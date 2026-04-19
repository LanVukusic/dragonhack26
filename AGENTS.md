# AGENTS.md - Agentic Coding Guidelines

This file provides guidance for agents operating in this repository.

---

## 1. Project Overview

Real-time puck/hockey tracking system:
- **Backend**: FastAPI server receiving circle positions via POST, detecting turns
- **Mock Camera**: Simulates realistic hockey movements for testing  
- **Frontend**: React + Konva displaying circles in real-time via WebSocket

Field size: 4000x3000 (all movement values must scale proportionally)

---

## 2. Build/Lint/Test Commands

### Backend (Python)
```bash
# Run backend server
python -m backend.main

# With uvicorn
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Run mock camera (6 modes)
python -m backend.mock_camera

# Run tests
pytest tests/ -v
pytest tests/test_file.py::test_name -v

# Type checking
mypy backend/
```

### Frontend (React/TypeScript)
```bash
cd web && npm install

# Dev server
cd web && npm run dev

# Build
cd web && npm run build

# Lint
cd web && npm run lint

# Type check
cd web && npx tsc --noEmit
```

---

## 3. Code Style Guidelines

### Python (Backend)

**Imports:** Stdlib first, then third-party, then local. No `from x import *`.

```python
# Correct
import asyncio
import logging
from typing import Dict, List, Optional

import numpy as np
from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
```

**Formatting:** Black-compatible (max line 100), type hints required, 4 spaces.

**Types:** Use Pydantic `BaseModel` for API schemas. Use `numpy` for positions.

```python
class CircleInput(BaseModel):
    id: int
    x: float
    y: float

# Using numpy for positions
new_pos = np.array([circle.x, circle.y])
delta = float(np.linalg.norm(new_pos - prev_pos))
```

**Naming:** `snake_case` functions/vars, `PascalCase` classes, `CONSTANTS`.

**Error Handling:** Use logging (`logger.info`, `logger.warning`, `logger.error`). Never expose stack traces.

---

### TypeScript/React (Frontend)

**Imports:** React first, then third-party, then local. Explicit named imports.

```typescript
import { useEffect, useState, useMemo } from "react";
import type { CircleData } from "./types/websocket";
import { CircleRenderer } from "./components/CircleRenderer";
```

**Formatting:** ESLint + Prettier, 2 spaces, max line 100.

**Types:** Define interfaces, avoid `any`.

```typescript
interface CircleData {
  id: number;
  x: number;
  y: number;
  in_frame: boolean;
}
```

**React Patterns:** Use `useMemo` for expensive ops, `useCallback` for handlers passed to children.

---

## 4. Critical Conventions (Do Not Change)

### Backend-Broadcasting Bug Fix
**ALWAYS broadcast RAW positions from POST data, NOT `TurnManager.get_current_state()`**

```python
# CORRECT
circles_list = [
    {"id": c.id, "x": c.x, "y": c.y, "in_frame": c.id in turn_manager.get_in_frame_ids()}
    for c in circles
]
await broadcast_to_frontends({"timestamp": ..., "circles": circles_list})
```

### Turn Detection Parameters
- Turn delay: 1.0s
- Cumulative movement threshold: 10.0px
- Min movement per update: 2.0px
- Missing timeout: 2000ms
- Motion blur threshold: 100.0px

### WebSocket URLs
- Dev: `ws://localhost:8000/ws`
- Production: same host as page
- Frontend auto-detects dev ports (5173/5174/3000/5175)

---

## 5. Key Files

```
backend/
├── main.py              # FastAPI + TurnManager + /api/tracker POST
├── mock_camera.py       # Mock camera (6 modes)
└── pyproject.toml      # Dependencies

web/
├── src/
│ ├── App.tsx         # Main app with WebSocket
│   ├── types/websocket.ts
│   └── components/
│       ├── CircleRenderer.tsx
│       └── ResponsiveStage.tsx  # 4000x3000 canvas
└── package.json
```

---

## 6. Common Patterns

### Adding New Turn Detection Mode
1. Add parameter to `TurnManager.__init__`
2. Add logic in `update()` method
3. Document in `pyproject.toml`

### Testing with Mock Camera
1. Start backend: `python -m backend.main`
2. Start mock: `python -m backend.mock_camera`
3. Select mode (1-6)
4. Frontend auto-connects via WebSocket

---

## 7. Debugging Tips

### Backend
- Enable INFO level for all movements
- `/api/game/state` returns full state
- Check `_movement_detected` flag

### Frontend
- Browser console shows WebSocket messages
- Connection status in UI (green/red)

### Common Issues
- Circles missing: check backend started, WebSocket URL
- Turn not detected: increase threshold or delay
- Motion blur false positives: increase threshold
- Out of frame wrongly: check missing_timeout_ms