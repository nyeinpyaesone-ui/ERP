"""
Inventory Management Serializers
=================================
DRF serializers for inventory models.
"""
from rest_framework import serializers
from .models import Warehouse, Category, Product, StockLevel, StockMovement


class WarehouseSerializer(serializers.ModelSerializer):
    """Serializer for Warehouse model."""
    
    class Meta:
        model = Warehouse
        fields = [
            'id', 'name', 'code', 'address', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model."""
    
    children_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'parent', 'description', 'children_count',
            'created_at'
        ]
        read_only_fields = ['created_at']
    
    def get_children_count(self, obj):
        return obj.children.count() if hasattr(obj, 'children') else 0


class ProductSerializer(serializers.ModelSerializer):
    """Serializer for Product model."""
    
    category_name = serializers.CharField(
        source='category.name',
        read_only=True
    )
    total_stock = serializers.ReadOnlyField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'sku', 'name', 'description', 'category',
            'category_name', 'unit_price', 'cost_price',
            'reorder_level', 'is_active', 'total_stock',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class StockLevelSerializer(serializers.ModelSerializer):
    """Serializer for StockLevel model."""
    
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    available_quantity = serializers.ReadOnlyField()
    
    class Meta:
        model = StockLevel
        fields = [
            'id', 'product', 'product_sku', 'product_name',
            'warehouse', 'warehouse_name', 'quantity',
            'reserved_quantity', 'available_quantity',
            'last_counted_at', 'updated_at'
        ]
        read_only_fields = ['updated_at']


class StockMovementSerializer(serializers.ModelSerializer):
    """Serializer for StockMovement model."""
    
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    
    class Meta:
        model = StockMovement
        fields = [
            'id', 'product', 'product_sku', 'product_name',
            'warehouse', 'warehouse_name', 'movement_type',
            'quantity', 'reference', 'notes', 'performed_by',
            'created_at'
        ]
        read_only_fields = ['created_at', 'performed_by']


class StockAdjustmentSerializer(serializers.Serializer):
    """Serializer for stock adjustment operations."""
    
    product_id = serializers.IntegerField()
    warehouse_id = serializers.IntegerField()
    movement_type = serializers.ChoiceField(choices=StockMovement.MOVEMENT_TYPES)
    quantity = serializers.IntegerField()
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        # Validate product exists
        try:
            Product.objects.get(id=data['product_id'])
        except Product.DoesNotExist:
            raise serializers.ValidationError({
                'product_id': 'Product does not exist'
            })
        
        # Validate warehouse exists
        try:
            Warehouse.objects.get(id=data['warehouse_id'])
        except Warehouse.DoesNotExist:
            raise serializers.ValidationError({
                'warehouse_id': 'Warehouse does not exist'
            })
        
        # Validate quantity for outbound movements
        if data['movement_type'] in ['OUT', 'TRANSFER_OUT']:
            try:
                stock_level = StockLevel.objects.get(
                    product_id=data['product_id'],
                    warehouse_id=data['warehouse_id']
                )
                if abs(data['quantity']) > stock_level.available_quantity:
                    raise serializers.ValidationError({
                        'quantity': 'Insufficient stock for this movement'
                    })
            except StockLevel.DoesNotExist:
                raise serializers.ValidationError({
                    'quantity': 'No stock available for this product in this warehouse'
                })
        
        return data
    
    def create(self, validated_data):
        return StockMovement.objects.create(**validated_data)
