# AI Demand Forecasting Module

## Overview
Machine learning-powered demand forecasting for inventory optimization.

## Features
- Time series forecasting (ARIMA, Prophet, LSTM)
- Seasonal trend analysis
- Automated reorder point calculation
- Stockout prediction
- Multi-warehouse demand balancing

## API Endpoints

### POST /api/v1/forecast/demand
Forecast demand for a product.

**Request:**
```json
{
  "product_id": "123",
  "warehouse_id": "wh-001",
  "horizon_days": 30,
  "model": "prophet"
}
```

**Response:**
```json
{
  "forecast": [
    {"date": "2026-07-01", "predicted_demand": 150, "confidence": 0.92},
    {"date": "2026-07-02", "predicted_demand": 145, "confidence": 0.89}
  ],
  "model_accuracy": 0.94,
  "recommended_reorder_point": 500
}
```

### GET /api/v1/forecast/accuracy
Get model accuracy metrics.

### POST /api/v1/forecast/reorder
Calculate optimal reorder points.

## Models
- **Prophet** — Facebook's forecasting tool (default)
- **ARIMA** — Autoregressive Integrated Moving Average
- **LSTM** — Deep learning for complex patterns
- **Ensemble** — Combined model for best accuracy

## Usage
```python
from app.forecasting import DemandForecaster

forecaster = DemandForecaster(model='prophet')
forecast = forecaster.predict(
    product_id='123',
    horizon_days=30
)
```

## Configuration
```env
FORECAST_MODEL=prophet
FORECAST_HORIZON=30
FORECAST_CONFIDENCE=0.95
```
