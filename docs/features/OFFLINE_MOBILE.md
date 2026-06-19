# Offline Mobile Mode

## Overview
Use the mobile app without internet connection.

## Features
- Local SQLite database sync
- Queue actions for later sync
- Offline maps and routing
- Cached product catalogs
- Background sync when online

## Architecture
```
┌─────────────────────────────────────┐
│           Mobile App                │
│  ┌──────────┐    ┌──────────┐      │
│  │  Online  │ ↔  │  Offline │      │
│  │  Mode    │    │  Mode    │      │
│  └──────────┘    └──────────┘      │
│       │                │             │
│  ┌────┴────┐      ┌───┴────┐       │
│  │ API     │      │ SQLite │       │
│  │ Server  │      │ Local  │       │
│  └─────────┘      └────────┘       │
└─────────────────────────────────────┘
```

## Sync Strategy
1. **Optimistic UI** — Show success immediately, sync in background
2. **Conflict Resolution** — Last-write-wins with manual override
3. **Batch Sync** — Queue changes, sync when connected
4. **Delta Sync** — Only sync changed data

## Implementation
```typescript
import { OfflineManager } from './offline';

const manager = new OfflineManager();

// Queue action for later
await manager.queueAction({
  type: 'CREATE_ORDER',
  data: {...},
  timestamp: Date.now()
});

// Sync when online
await manager.sync();
```

## Configuration
```env
OFFLINE_MODE=true
SYNC_INTERVAL=300000  # 5 minutes
MAX_OFFLINE_DAYS=7
```
