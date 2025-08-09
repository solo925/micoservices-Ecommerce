#!/bin/bash

# E-commerce Microservices Kubernetes Deployment Script

set -e

echo "🚀 Starting E-commerce Microservices Deployment"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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
print_status "Creating namespaces..."
kubectl apply -f namespace.yaml

# Deploy infrastructure components
print_status "Deploying PostgreSQL..."
kubectl apply -f postgres.yaml

print_status "Deploying Redis..."
kubectl apply -f redis.yaml

# Wait for infrastructure to be ready
print_status "Waiting for infrastructure to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/postgres -n ecommerce
kubectl wait --for=condition=available --timeout=300s deployment/redis -n ecommerce

# Deploy microservices
print_status "Deploying microservices..."
kubectl apply -f microservices.yaml

# Deploy API Gateway
print_status "Deploying API Gateway..."
kubectl apply -f gateway.yaml

# Deploy monitoring stack
print_status "Deploying monitoring stack..."
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
print_status "Service Information:"
echo ""
echo "📊 Monitoring Services:"
echo "- Grafana: http://grafana.ecommerce.local (admin/admin)"
echo "- Prometheus: http://prometheus.ecommerce.local"
echo "- Jaeger: http://jaeger.ecommerce.local"
echo ""
echo "🔗 API Endpoints:"
echo "- API Gateway: http://ecommerce.local/api/gateway/"
echo "- Products API: http://ecommerce.local/api/products/"
echo "- Orders API: http://ecommerce.local/api/orders/"
echo "- Payments API: http://ecommerce.local/api/payments/"
echo "- Inventory API: http://ecommerce.local/api/inventory/"
echo "- Auth API: http://ecommerce.local/api/auth/"
echo ""
echo "🎯 GraphQL Playground: http://ecommerce.local/api/gateway/graphql/"
echo ""

# Display pod status
print_status "Pod Status:"
kubectl get pods -n ecommerce
echo ""
kubectl get pods -n ecommerce-monitoring

# Display service status
print_status "Service Status:"
kubectl get services -n ecommerce
echo ""
kubectl get services -n ecommerce-monitoring

# Display HPA status
print_status "Horizontal Pod Autoscaler Status:"
kubectl get hpa -n ecommerce

echo ""
print_status "🎉 Deployment completed successfully!"
print_warning "Note: Add the following entries to your /etc/hosts file for local testing:"
echo "127.0.0.1 ecommerce.local"
echo "127.0.0.1 api.ecommerce.local"
echo "127.0.0.1 grafana.ecommerce.local"
echo "127.0.0.1 prometheus.ecommerce.local"
echo "127.0.0.1 jaeger.ecommerce.local"
