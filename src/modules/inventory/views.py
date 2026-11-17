"""
Inventory Management Views
===========================
API views for inventory operations.
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, F
from django_filters.rest_framework import DjangoFilterBackend

from .models import Warehouse, Category, Product, StockLevel, StockMovement
from .serializers import (
    WarehouseSerializer,
    CategorySerializer,
    ProductSerializer,
    StockLevelSerializer,
    StockMovementSerializer,
    StockAdjustmentSerializer,
)


class WarehouseViewSet(viewsets.ModelViewSet):
    """ViewSet for warehouse management."""
    
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'address']
    ordering_fields = ['name', 'code', 'created_at']


class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for product category management."""
    
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']


class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for product management."""
    
    queryset = Product.objects.select_related('category').all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['sku', 'name', 'description']
    ordering_fields = ['name', 'sku', 'unit_price', 'created_at']

    @action(detail=True, methods=['get'])
    def stock_summary(self, request, pk=None):
        """Get stock summary for a product across all warehouses."""
        product = self.get_object()
        stock_levels = StockLevel.objects.filter(
            product=product
        ).select_related('warehouse')
        
        summary = {
            'product': ProductSerializer(product).data,
            'total_stock': sum(sl.quantity for sl in stock_levels),
            'total_reserved': sum(sl.reserved_quantity for sl in stock_levels),
            'warehouses': StockLevelSerializer(stock_levels, many=True).data,
        }
        
        return Response(summary)


class StockLevelViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing stock levels."""
    
    queryset = StockLevel.objects.select_related('product', 'warehouse').all()
    serializer_class = StockLevelSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['product', 'warehouse']
    ordering_fields = ['quantity', 'updated_at']

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get products with stock below reorder level."""
        low_stock_items = StockLevel.objects.filter(
            quantity__lte=F('product__reorder_level')
        ).select_related('product', 'warehouse')
        
        serializer = self.get_serializer(low_stock_items, many=True)
        return Response(serializer.data)


class StockMovementViewSet(viewsets.ModelViewSet):
    """ViewSet for stock movement tracking."""
    
    queryset = StockMovement.objects.select_related(
        'product', 'warehouse'
    ).all().order_by('-created_at')
    serializer_class = StockMovementSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['product', 'warehouse', 'movement_type']
    ordering_fields = ['created_at']

    @action(detail=False, methods=['post'])
    def adjust_stock(self, request):
        """Perform stock adjustment."""
        serializer = StockAdjustmentSerializer(data=request.data)
        
        if serializer.is_valid():
            movement = serializer.save(performed_by=request.user.username)
            return Response(
                StockMovementSerializer(movement).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
