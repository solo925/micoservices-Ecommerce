#!/bin/bash

# Distributed Database Deployment Script for E-commerce Microservices

set -e

echo "🚀 Starting Distributed Database Deployment"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl is not installed. Please install kubectl first."
    exit 1
fi

# Check if cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    print_error "Cannot connect to Kubernetes cluster. Please check your kubectl configuration."
    exit 1
fi

print_status "Connected to Kubernetes cluster"

# Create namespaces
print_step "Creating namespaces..."
kubectl apply -f namespace.yaml

# Deploy distributed PostgreSQL
print_step "Deploying distributed PostgreSQL databases..."
kubectl apply -f postgres-distributed.yaml

# Wait for PostgreSQL to be ready
print_status "Waiting for distributed PostgreSQL to be ready..."
kubectl wait --for=condition=available --timeout=600s statefulset/postgres-distributed -n ecommerce

# Deploy Redis
print_step "Deploying Redis..."
kubectl apply -f redis.yaml

# Wait for Redis to be ready
print_status "Waiting for Redis to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/redis -n ecommerce

# Deploy microservices with distributed database configuration
print_step "Deploying microservices with distributed database configuration..."
kubectl apply -f microservices-distributed.yaml

# Deploy API Gateway
print_step "Deploying API Gateway..."
kubectl apply -f gateway.yaml

# Deploy monitoring stack
print_step "Deploying monitoring stack..."
kubectl apply -f monitoring-stack.yaml

# Check if Istio is installed
if kubectl get namespace istio-system &> /dev/null; then
    print_status "Istio detected. Deploying Istio configurations..."
    kubectl apply -f istio/gateway.yaml
    kubectl apply -f istio/virtual-service.yaml
    kubectl apply -f istio/security-policies.yaml
else
    print_warning "Istio not detected. Deploying NGINX Ingress instead..."
    kubectl apply -f ingress.yaml
fi

# Wait for deployments to be ready
print_status "Waiting for deployments to be ready..."

# Wait for microservices
kubectl wait --for=condition=available --timeout=600s deployment/gateway -n ecommerce
kubectl wait --for=condition=available --timeout=600s deployment/products -n ecommerce
kubectl wait --for=condition=available --timeout=600s deployment/orders -n ecommerce
kubectl wait --for=condition=available --timeout=600s deployment/payments -n ecommerce
kubectl wait --for=condition=available --timeout=600s deployment/inventory -n ecommerce
kubectl wait --for=condition=available --timeout=600s deployment/auth -n ecommerce

# Wait for monitoring
kubectl wait --for=condition=available --timeout=300s deployment/prometheus -n ecommerce-monitoring
kubectl wait --for=condition=available --timeout=300s deployment/grafana -n ecommerce-monitoring
kubectl wait --for=condition=available --timeout=300s deployment/jaeger -n ecommerce-monitoring

print_status "All deployments are ready!"

# Display service information
print_step "Service Information:"
echo "=================================="

# Database services
echo "📊 Database Services:"
kubectl get services -n ecommerce | grep postgres
echo ""

# Microservice deployments
echo "🔧 Microservice Deployments:"
kubectl get deployments -n ecommerce
echo ""

# Pod status
echo "📦 Pod Status:"
kubectl get pods -n ecommerce
echo ""

# Storage information
echo "💾 Storage Information:"
kubectl get pvc -n ecommerce
echo ""

print_status "Distributed database deployment completed successfully!"
echo ""
print_warning "Important Notes:"
echo "1. Each microservice now has its own database"
echo "2. Cross-service data access is handled through the DataSyncService"
echo "3. Use the migration script to transfer existing data"
echo "4. Monitor database performance and connections"
echo ""
print_status "Next steps:"
echo "1. Run the migration script: python scripts/migrate_to_distributed_db.py"
echo "2. Test all microservices with their new databases"
echo "3. Verify cross-service data access is working"
echo "4. Monitor performance and adjust resources as needed"
