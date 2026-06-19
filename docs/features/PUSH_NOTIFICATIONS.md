# Push Notifications

## Overview
Real-time notifications for mobile and web.

## Features
- Order status updates
- Low stock alerts
- Approval requests
- System announcements
- Custom user preferences

## Channels
| Channel | Platform | Use Case |
|---------|----------|----------|
| Firebase FCM | Android | Push notifications |
| APNs | iOS | Push notifications |
| Web Push | Browser | Desktop alerts |
| WebSocket | All | Real-time updates |
| Email | All | Digest summaries |

## API Endpoints

### POST /api/v1/notifications/send
Send a notification.

**Request:**
```json
{
  "user_ids": ["123", "456"],
  "title": "Low Stock Alert",
  "body": "Product XYZ is below reorder point",
  "type": "inventory_alert",
  "data": {"product_id": "xyz", "current_stock": 5}
}
```

### GET /api/v1/notifications/preferences
Get user notification preferences.

### PUT /api/v1/notifications/preferences
Update preferences.

## Implementation
```typescript
import { NotificationManager } from './notifications';

const manager = new NotificationManager();

// Request permission
await manager.requestPermission();

// Subscribe to topic
await manager.subscribe('inventory_alerts');

// Handle incoming
manager.onMessage((payload) => {
  showToast(payload.title, payload.body);
});
```
