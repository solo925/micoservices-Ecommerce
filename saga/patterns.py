import uuid
import json
import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Callable, Any, Optional, Union
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import redis
from django.conf import settings
from django.utils import timezone
from django.db import transaction, models

logger = logging.getLogger(__name__)


class SagaState(Enum):
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


class StepState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


@dataclass
class SagaContext:
    """Context shared across saga steps"""
    saga_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def set(self, key: str, value: Any):
        """Set a value in the context"""
        self.data[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the context"""
        return self.data.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary"""
        return {
            'saga_id': self.saga_id,
            'data': self.data,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SagaContext':
        """Create context from dictionary"""
        return cls(
            saga_id=data['saga_id'],
            data=data.get('data', {}),
            metadata=data.get('metadata', {}),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
        )


class SagaStep(ABC):
    """Abstract base class for saga steps"""
    
    def __init__(self, name: str, timeout: int = 30):
        self.name = name
        self.timeout = timeout
        self.state = StepState.PENDING
        self.error_message = None
        self.retry_count = 0
        self.max_retries = 3
    
    @abstractmethod
    async def execute(self, context: SagaContext) -> Any:
        """Execute the step"""
        pass
    
    @abstractmethod
    async def compensate(self, context: SagaContext) -> Any:
        """Compensate the step (undo its effects)"""
        pass
    
    async def run(self, context: SagaContext) -> Any:
        """Run the step with error handling and retries"""
        self.state = StepState.RUNNING
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Executing step {self.name} (attempt {attempt + 1})")
                result = await asyncio.wait_for(
                    self.execute(context),
                    timeout=self.timeout
                )
                self.state = StepState.COMPLETED
                logger.info(f"Step {self.name} completed successfully")
                return result
                
            except asyncio.TimeoutError:
                error_msg = f"Step {self.name} timed out after {self.timeout}s"
                logger.error(error_msg)
                self.error_message = error_msg
                
                if attempt < self.max_retries:
                    self.retry_count += 1
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    self.state = StepState.FAILED
                    raise SagaStepException(error_msg)
                    
            except Exception as e:
                error_msg = f"Step {self.name} failed: {str(e)}"
                logger.error(error_msg)
                self.error_message = error_msg
                
                if attempt < self.max_retries and self._is_retryable_error(e):
                    self.retry_count += 1
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    self.state = StepState.FAILED
                    raise SagaStepException(error_msg)
    
    async def compensate_step(self, context: SagaContext) -> Any:
        """Run compensation with error handling"""
        self.state = StepState.COMPENSATING
        
        try:
            logger.info(f"Compensating step {self.name}")
            result = await asyncio.wait_for(
                self.compensate(context),
                timeout=self.timeout
            )
            self.state = StepState.COMPENSATED
            logger.info(f"Step {self.name} compensated successfully")
            return result
            
        except Exception as e:
            error_msg = f"Compensation for step {self.name} failed: {str(e)}"
            logger.error(error_msg)
            self.error_message = error_msg
            raise SagaCompensationException(error_msg)
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable"""
        # Define retryable error types
        retryable_errors = (
            ConnectionError,
            TimeoutError,
            # Add more retryable errors as needed
        )
        return isinstance(error, retryable_errors)


class Saga:
    """SAGA orchestrator for distributed transactions"""
    
    def __init__(self, name: str, steps: List[SagaStep], context: SagaContext = None):
        self.name = name
        self.steps = steps
        self.saga_id = str(uuid.uuid4()) if not context else context.saga_id
        self.context = context or SagaContext(saga_id=self.saga_id)
        self.state = SagaState.STARTED
        self.current_step_index = 0
        self.completed_steps: List[SagaStep] = []
        self.error_message = None
        self.started_at = datetime.now()
        self.completed_at = None
        
        # Redis for persistence
        self.redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
    
    async def execute(self) -> SagaContext:
        """Execute the saga"""
        self.state = SagaState.RUNNING
        await self._persist_state()
        
        try:
            logger.info(f"Starting saga {self.name} with ID {self.saga_id}")
            
            # Execute each step
            for i, step in enumerate(self.steps):
                self.current_step_index = i
                await self._persist_state()
                
                try:
                    await step.run(self.context)
                    self.completed_steps.append(step)
                    
                except SagaStepException as e:
                    logger.error(f"Saga {self.name} failed at step {step.name}: {e}")
                    self.error_message = str(e)
                    await self._compensate()
                    return self.context
            
            # All steps completed successfully
            self.state = SagaState.COMPLETED
            self.completed_at = datetime.now()
            await self._persist_state()
            
            logger.info(f"Saga {self.name} completed successfully")
            return self.context
            
        except Exception as e:
            logger.error(f"Saga {self.name} failed with unexpected error: {e}")
            self.error_message = str(e)
            self.state = SagaState.FAILED
            await self._persist_state()
            raise SagaException(f"Saga {self.name} failed: {e}")
    
    async def _compensate(self):
        """Compensate completed steps in reverse order"""
        self.state = SagaState.COMPENSATING
        await self._persist_state()
        
        logger.info(f"Starting compensation for saga {self.name}")
        
        # Compensate in reverse order
        for step in reversed(self.completed_steps):
            try:
                await step.compensate_step(self.context)
                
            except SagaCompensationException as e:
                logger.error(f"Compensation failed for step {step.name}: {e}")
                # Continue with other compensations even if one fails
                # In production, you might want to implement more sophisticated error handling
        
        self.state = SagaState.COMPENSATED
        self.completed_at = datetime.now()
        await self._persist_state()
        
        logger.info(f"Saga {self.name} compensation completed")
    
    async def _persist_state(self):
        """Persist saga state to Redis"""
        try:
            saga_data = {
                'saga_id': self.saga_id,
                'name': self.name,
                'state': self.state.value,
                'current_step_index': self.current_step_index,
                'context': self.context.to_dict(),
                'error_message': self.error_message,
                'started_at': self.started_at.isoformat(),
                'completed_at': self.completed_at.isoformat() if self.completed_at else None,
                'steps': [
                    {
                        'name': step.name,
                        'state': step.state.value,
                        'error_message': step.error_message,
                        'retry_count': step.retry_count
                    }
                    for step in self.steps
                ]
            }
            
            key = f"saga:{self.saga_id}"
            self.redis_client.setex(key, 3600, json.dumps(saga_data))  # 1 hour TTL
            
        except Exception as e:
            logger.error(f"Failed to persist saga state: {e}")
    
    @classmethod
    async def recover(cls, saga_id: str) -> Optional['Saga']:
        """Recover a saga from persisted state"""
        try:
            redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
            key = f"saga:{saga_id}"
            saga_data = redis_client.get(key)
            
            if not saga_data:
                return None
            
            data = json.loads(saga_data)
            
            # This is a simplified recovery - in production you'd need to reconstruct the steps
            # For now, return the saga data as a dict
            return data
            
        except Exception as e:
            logger.error(f"Failed to recover saga {saga_id}: {e}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get current saga status"""
        return {
            'saga_id': self.saga_id,
            'name': self.name,
            'state': self.state.value,
            'current_step': self.current_step_index,
            'total_steps': len(self.steps),
            'completed_steps': len(self.completed_steps),
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'context': self.context.to_dict(),
            'steps': [
                {
                    'name': step.name,
                    'state': step.state.value,
                    'error_message': step.error_message,
                    'retry_count': step.retry_count
                }
                for step in self.steps
            ]
        }


# Concrete implementations for e-commerce operations

class ReserveInventoryStep(SagaStep):
    """Reserve inventory for order items"""
    
    def __init__(self):
        super().__init__("reserve_inventory")
    
    async def execute(self, context: SagaContext) -> Any:
        """Reserve inventory for order items"""
        order_items = context.get('order_items', [])
        reservations = []
        
        for item in order_items:
            # Simulate inventory reservation
            from inventory.services import InventoryService
            
            try:
                # Reserve inventory (this would be a synchronous call wrapped in async)
                reservation = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._reserve_item,
                    item['product_id'],
                    item['quantity']
                )
                reservations.append(reservation)
                
            except Exception as e:
                # Clean up any successful reservations
                for res in reservations:
                    try:
                        await asyncio.get_event_loop().run_in_executor(
                            None,
                            self._release_reservation,
                            res['reservation_id']
                        )
                    except:
                        pass
                raise e
        
        context.set('inventory_reservations', reservations)
        return reservations
    
    async def compensate(self, context: SagaContext) -> Any:
        """Release inventory reservations"""
        reservations = context.get('inventory_reservations', [])
        
        for reservation in reservations:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._release_reservation,
                    reservation['reservation_id']
                )
            except Exception as e:
                logger.error(f"Failed to release reservation {reservation['reservation_id']}: {e}")
    
    def _reserve_item(self, product_id: str, quantity: int) -> Dict[str, Any]:
        """Reserve inventory item (sync method)"""
        from inventory.models import InventoryItem, StockReservation
        
        try:
            with transaction.atomic():
                inventory_item = InventoryItem.objects.select_for_update().get(
                    product_id=product_id
                )
                
                if inventory_item.quantity_available < quantity:
                    raise ValueError(f"Insufficient inventory for product {product_id}")
                
                # Create reservation
                reservation = StockReservation.objects.create(
                    product_id=product_id,
                    quantity=quantity,
                    reserved_until=timezone.now() + timedelta(minutes=30)
                )
                
                # Update available quantity
                inventory_item.quantity_available -= quantity
                inventory_item.quantity_reserved += quantity
                inventory_item.save()
                
                return {
                    'reservation_id': str(reservation.id),
                    'product_id': product_id,
                    'quantity': quantity
                }
                
        except Exception as e:
            logger.error(f"Failed to reserve inventory for product {product_id}: {e}")
            raise
    
    def _release_reservation(self, reservation_id: str):
        """Release inventory reservation (sync method)"""
        from inventory.models import InventoryItem, StockReservation
        
        try:
            with transaction.atomic():
                reservation = StockReservation.objects.select_for_update().get(
                    id=reservation_id
                )
                
                inventory_item = InventoryItem.objects.select_for_update().get(
                    product_id=reservation.product_id
                )
                
                # Restore available quantity
                inventory_item.quantity_available += reservation.quantity
                inventory_item.quantity_reserved -= reservation.quantity
                inventory_item.save()
                
                # Delete reservation
                reservation.delete()
                
        except Exception as e:
            logger.error(f"Failed to release reservation {reservation_id}: {e}")
            raise


class CreateOrderStep(SagaStep):
    """Create order in the system"""
    
    def __init__(self):
        super().__init__("create_order")
    
    async def execute(self, context: SagaContext) -> Any:
        """Create order"""
        order_data = context.get('order_data')
        
        order = await asyncio.get_event_loop().run_in_executor(
            None,
            self._create_order,
            order_data
        )
        
        context.set('order_id', str(order['id']))
        context.set('order', order)
        return order
    
    async def compensate(self, context: SagaContext) -> Any:
        """Cancel/delete order"""
        order_id = context.get('order_id')
        
        if order_id:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._cancel_order,
                order_id
            )
    
    def _create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create order (sync method)"""
        from orders.models import Order, OrderItem
        
        try:
            with transaction.atomic():
                # Create order
                order = Order.objects.create(
                    customer_name=order_data['customer_name'],
                    customer_email=order_data['customer_email'],
                    status='pending',
                    subtotal=order_data['subtotal'],
                    total_amount=order_data['total_amount']
                )
                
                # Create order items
                for item_data in order_data['items']:
                    OrderItem.objects.create(
                        order=order,
                        product_id=item_data['product_id'],
                        quantity=item_data['quantity'],
                        unit_price=item_data['unit_price'],
                        total_price=item_data['total_price']
                    )
                
                return {
                    'id': order.id,
                    'order_number': order.order_number,
                    'status': order.status,
                    'total_amount': float(order.total_amount)
                }
                
        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            raise
    
    def _cancel_order(self, order_id: str):
        """Cancel order (sync method)"""
        from orders.models import Order
        
        try:
            order = Order.objects.get(id=order_id)
            order.status = 'cancelled'
            order.save()
            
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise


class ProcessPaymentStep(SagaStep):
    """Process payment for the order"""
    
    def __init__(self):
        super().__init__("process_payment")
    
    async def execute(self, context: SagaContext) -> Any:
        """Process payment"""
        order = context.get('order')
        payment_data = context.get('payment_data')
        
        payment = await asyncio.get_event_loop().run_in_executor(
            None,
            self._process_payment,
            order,
            payment_data
        )
        
        context.set('payment_id', str(payment['id']))
        context.set('payment', payment)
        return payment
    
    async def compensate(self, context: SagaContext) -> Any:
        """Refund payment"""
        payment_id = context.get('payment_id')
        
        if payment_id:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._refund_payment,
                payment_id
            )
    
    def _process_payment(self, order: Dict[str, Any], payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment (sync method)"""
        from payments.models import Payment
        
        try:
            with transaction.atomic():
                payment = Payment.objects.create(
                    order_id=order['id'],
                    amount=order['total_amount'],
                    currency='USD',
                    provider='stripe',
                    status='processing',
                    provider_transaction_id=f"txn_{uuid.uuid4()}",
                    payment_method_type=payment_data.get('payment_method', 'card')
                )
                
                # Simulate payment processing
                # In real implementation, this would call payment provider API
                payment.status = 'completed'
                payment.save()
                
                return {
                    'id': payment.id,
                    'status': payment.status,
                    'amount': float(payment.amount),
                    'transaction_id': payment.provider_transaction_id
                }
                
        except Exception as e:
            logger.error(f"Failed to process payment: {e}")
            raise
    
    def _refund_payment(self, payment_id: str):
        """Refund payment (sync method)"""
        from payments.models import Payment, Refund
        
        try:
            with transaction.atomic():
                payment = Payment.objects.get(id=payment_id)
                
                # Create refund
                refund = Refund.objects.create(
                    payment=payment,
                    amount=payment.amount,
                    reason='order_cancelled',
                    status='processing'
                )
                
                # Simulate refund processing
                refund.status = 'completed'
                refund.save()
                
                payment.status = 'refunded'
                payment.save()
                
        except Exception as e:
            logger.error(f"Failed to refund payment {payment_id}: {e}")
            raise


class ConfirmInventoryStep(SagaStep):
    """Confirm inventory allocation and reduce stock"""
    
    def __init__(self):
        super().__init__("confirm_inventory")
    
    async def execute(self, context: SagaContext) -> Any:
        """Confirm inventory allocation"""
        reservations = context.get('inventory_reservations', [])
        
        confirmations = await asyncio.get_event_loop().run_in_executor(
            None,
            self._confirm_reservations,
            reservations
        )
        
        context.set('inventory_confirmations', confirmations)
        return confirmations
    
    async def compensate(self, context: SagaContext) -> Any:
        """Restore inventory (this shouldn't happen if payment was successful)"""
        confirmations = context.get('inventory_confirmations', [])
        
        for confirmation in confirmations:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._restore_inventory,
                    confirmation
                )
            except Exception as e:
                logger.error(f"Failed to restore inventory: {e}")
    
    def _confirm_reservations(self, reservations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Confirm inventory reservations (sync method)"""
        from inventory.models import InventoryItem, StockReservation, StockMovement
        
        confirmations = []
        
        try:
            with transaction.atomic():
                for reservation in reservations:
                    reservation_obj = StockReservation.objects.get(
                        id=reservation['reservation_id']
                    )
                    
                    inventory_item = InventoryItem.objects.select_for_update().get(
                        product_id=reservation['product_id']
                    )
                    
                    # Reduce reserved quantity and increase sold quantity
                    inventory_item.quantity_reserved -= reservation['quantity']
                    inventory_item.quantity_sold += reservation['quantity']
                    inventory_item.save()
                    
                    # Create stock movement record
                    movement = StockMovement.objects.create(
                        product_id=reservation['product_id'],
                        movement_type='OUT',
                        quantity=reservation['quantity'],
                        reason='sale_confirmed'
                    )
                    
                    # Delete reservation
                    reservation_obj.delete()
                    
                    confirmations.append({
                        'product_id': reservation['product_id'],
                        'quantity': reservation['quantity'],
                        'movement_id': str(movement.id)
                    })
            
            return confirmations
            
        except Exception as e:
            logger.error(f"Failed to confirm inventory reservations: {e}")
            raise
    
    def _restore_inventory(self, confirmation: Dict[str, Any]):
        """Restore inventory (sync method)"""
        from inventory.models import InventoryItem, StockMovement
        
        try:
            with transaction.atomic():
                inventory_item = InventoryItem.objects.select_for_update().get(
                    product_id=confirmation['product_id']
                )
                
                # Restore quantities
                inventory_item.quantity_available += confirmation['quantity']
                inventory_item.quantity_sold -= confirmation['quantity']
                inventory_item.save()
                
                # Create reverse movement
                StockMovement.objects.create(
                    product_id=confirmation['product_id'],
                    movement_type='IN',
                    quantity=confirmation['quantity'],
                    reason='sale_cancelled'
                )
                
        except Exception as e:
            logger.error(f"Failed to restore inventory: {e}")
            raise


class SendNotificationStep(SagaStep):
    """Send order confirmation notification"""
    
    def __init__(self):
        super().__init__("send_notification")
    
    async def execute(self, context: SagaContext) -> Any:
        """Send notification"""
        order = context.get('order')
        payment = context.get('payment')
        
        notification = await asyncio.get_event_loop().run_in_executor(
            None,
            self._send_notification,
            order,
            payment
        )
        
        context.set('notification_id', notification['id'])
        return notification
    
    async def compensate(self, context: SagaContext) -> Any:
        """Send cancellation notification"""
        order = context.get('order')
        
        if order:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._send_cancellation_notification,
                order
            )
    
    def _send_notification(self, order: Dict[str, Any], payment: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification (sync method)"""
        from notification.services import NotificationService
        
        try:
            notification_service = NotificationService()
            
            notification = notification_service.send_notification(
                recipient_email=order.get('customer_email'),
                template_name='order_confirmation',
                context={
                    'order_id': order['id'],
                    'order_number': order['order_number'],
                    'total_amount': order['total_amount'],
                    'payment_id': payment['transaction_id']
                },
                channels=['email']
            )
            
            return {
                'id': str(notification.id),
                'status': 'sent'
            }
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            # Don't fail the saga for notification failures
            return {'id': 'failed', 'status': 'failed'}
    
    def _send_cancellation_notification(self, order: Dict[str, Any]):
        """Send cancellation notification (sync method)"""
        from notification.services import NotificationService
        
        try:
            notification_service = NotificationService()
            
            notification_service.send_notification(
                recipient_email=order.get('customer_email'),
                template_name='order_cancelled',
                context={
                    'order_id': order['id'],
                    'order_number': order['order_number']
                },
                channels=['email']
            )
            
        except Exception as e:
            logger.error(f"Failed to send cancellation notification: {e}")


# Saga orchestrator for order processing
class OrderProcessingSaga:
    """Order processing saga orchestrator"""
    
    @staticmethod
    async def create_order(order_data: Dict[str, Any], payment_data: Dict[str, Any]) -> SagaContext:
        """Create order with SAGA pattern"""
        
        # Create saga context
        context = SagaContext(saga_id=str(uuid.uuid4()))
        context.set('order_data', order_data)
        context.set('order_items', order_data['items'])
        context.set('payment_data', payment_data)
        
        # Define saga steps
        steps = [
            ReserveInventoryStep(),
            CreateOrderStep(),
            ProcessPaymentStep(),
            ConfirmInventoryStep(),
            SendNotificationStep()
        ]
        
        # Create and execute saga
        saga = Saga("order_processing", steps, context)
        
        try:
            result_context = await saga.execute()
            return result_context
            
        except SagaException as e:
            logger.error(f"Order processing saga failed: {e}")
            raise
    
    @staticmethod
    def get_saga_status(saga_id: str) -> Optional[Dict[str, Any]]:
        """Get saga status"""
        try:
            redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
            key = f"saga:{saga_id}"
            saga_data = redis_client.get(key)
            
            if saga_data:
                return json.loads(saga_data)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get saga status: {e}")
            return None


# Custom exceptions
class SagaException(Exception):
    """Base exception for saga errors"""
    pass


class SagaStepException(Exception):
    """Exception for saga step failures"""
    pass


class SagaCompensationException(Exception):
    """Exception for saga compensation failures"""
    pass
