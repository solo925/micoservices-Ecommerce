import graphene
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from . import resolvers
from .schema import schema


class GraphQLView(View):
    """GraphQL endpoint for the API Gateway"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request):
        """Handle GraphQL queries"""
        try:
            data = request.POST.get('query') or request.body.decode('utf-8')
            if isinstance(data, str):
                # Parse the query
                result = schema.execute(data)
                if result.errors:
                    return JsonResponse({
                        'errors': [str(error) for error in result.errors]
                    }, status=400)
                return JsonResponse({'data': result.data})
            else:
                return JsonResponse({'error': 'Invalid query'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def get(self, request):
        """Handle GraphQL introspection queries"""
        return JsonResponse({
            'message': 'GraphQL Gateway is running. Use POST for queries.',
            'endpoint': '/api/gateway/graphql/',
            'timestamp': timezone.now().isoformat()
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint for the API Gateway"""
    return Response({
        'status': 'healthy',
        'service': 'gateway',
        'timestamp': timezone.now().isoformat(),
        'endpoints': {
            'graphql': '/api/gateway/graphql/',
            'health': '/api/gateway/health/'
        }
    }, status=status.HTTP_200_OK)
