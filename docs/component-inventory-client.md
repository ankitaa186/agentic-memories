# Component Inventory - Web UI (Client)

**Part:** Web UI (client)
**Framework:** React 18.3.1 + TypeScript 5.6.2
**Build Tool:** Vite 5.4.8
**Styling:** Tailwind CSS 3.4.13

---

## Application Structure

### Pages (Route Components)

#### Store.tsx
**Route:** `/store`
**Purpose:** Memory ingestion interface
**Features:**
- Form for entering conversation history
- User ID input
- Submit to `/v1/store` endpoint
- Display extraction results and created memories
- View memory types (episodic, semantic, procedural, emotional, portfolio)

#### Retrieve.tsx
**Route:** `/retrieve`
**Purpose:** Memory search and retrieval interface
**Features:**
- Search query input
- User ID filter
- Layer filter (short-term, semantic, episodic)
- Type filter (explicit, implicit)
- Results display with semantic similarity scores
- Pagination controls (limit/offset)

#### Browser.tsx
**Route:** `/browser`
**Purpose:** Visual timeline memory browser
**Features:**
- Timeline view of all memories
- Memory card display
- Filtering and sorting capabilities
- Visual memory exploration

#### Structured.tsx
**Route:** `/structured`
**Purpose:** Categorized memory view
**Features:**
- LLM-organized memory categories
- Displays memories grouped by:
  - Emotions
  - Behaviors
  - Personal
  - Professional
  - Habits
  - Skills & Tools
  - Projects
  - Relationships
  - Learning Journal
  - Finance
  - Other
- Category-based navigation

#### Health.tsx
**Route:** `/health`
**Purpose:** Service health monitoring dashboard
**Features:**
- Real-time service status checks
- Database connectivity status (ChromaDB, TimescaleDB, Redis)
- Environment validation
- Portfolio service status
- Langfuse integration status
- Visual health indicators (ok/degraded/down)

#### AppLayout.tsx
**Purpose:** Main application layout wrapper
**Features:**
- Navigation sidebar/header
- Route-based navigation
- Responsive layout structure
- Consistent page structure

---

### Components

#### DevConsole.tsx
**Purpose:** Debug console for development
**Features:**
- Developer debugging tools
- Collapsible console panel
- Log viewing
- Debug information display
- Uses Radix UI Collapsible component

---

### Library Utilities

#### lib/api.ts
**Purpose:** API client abstraction
**Features:**
- Centralized API calls to backend
- HTTP client wrapper (likely using fetch or axios)
- Request/response handling
- Error handling
- Type-safe API methods

**Endpoints Called:**
- `/v1/store` - POST memory storage
- `/v1/retrieve` - GET memory retrieval
- `/v1/retrieve/structured` - POST structured retrieval
- `/health/full` - GET health check

#### lib/devlog.ts
**Purpose:** Development logging utility
**Features:**
- Console logging abstraction
- Environment-aware logging (dev vs prod)
- Structured log formatting

---

### Entry Point

#### main.tsx
**Purpose:** Application bootstrap
**Features:**
- React app initialization
- Router setup (React Router)
- Root component mounting
- Global providers (TanStack Query)

---

## State Management

### TanStack Query (React Query)
**Purpose:** Server state management and caching
**Usage:**
- API data fetching
- Automatic cache invalidation
- Background refetching
- Optimistic updates
- Loading/error states

**Benefits:**
- Eliminates need for Redux
- Built-in caching layer
- Automatic request deduplication
- Stale-while-revalidate patterns

---

## Routing Structure

```
/ (root)
├─ /store           → Store.tsx
├─ /retrieve        → Retrieve.tsx
├─ /browser         → Browser.tsx
├─ /structured      → Structured.tsx
└─ /health          → Health.tsx
```

**Router:** React Router 6.26.2
**Navigation:** Client-side routing (SPA)

---

## Styling System

### Tailwind CSS
**Version:** 3.4.13
**Configuration:** `tailwind.config.js`
**Features:**
- Utility-first CSS
- Responsive design utilities
- Custom color palette
- Typography system
- Spacing and layout utilities

### PostCSS
**Version:** 8.4.47
**Purpose:** CSS processing pipeline
**Plugins:**
- Tailwind CSS processor
- Autoprefixer for browser compatibility

---

## UI Component Library

### Radix UI
**Components Used:**
- `@radix-ui/react-collapsible` - Collapsible panels (DevConsole)

**Benefits:**
- Accessible by default
- Unstyled primitives (style with Tailwind)
- Keyboard navigation support
- ARIA attributes built-in

---

## Testing

### Playwright
**Version:** 1.47.2
**Purpose:** End-to-end browser testing
**Test Files:** `ui/tests/`
**Features:**
- Cross-browser testing
- Page object pattern
- Visual regression testing
- API mocking capabilities

**Test Command:** `npm run test:e2e`

---

## Build Configuration

### Vite Config
**Features:**
- Fast HMR (Hot Module Replacement)
- TypeScript compilation
- React Fast Refresh
- Production optimizations
- Asset bundling

**Build Commands:**
- `npm run dev` - Development server (port 5173)
- `npm run build` - Production build
- `npm run preview` - Preview production build

---

## Component Patterns

### Page Components
**Pattern:** Functional components with hooks
**State:** TanStack Query for server state, local useState for UI state
**Styling:** Tailwind utility classes
**TypeScript:** Strict typing with interfaces

### API Integration
**Pattern:** Custom hooks wrapping TanStack Query
**Error Handling:** Error boundaries and fallback UI
**Loading States:** Skeleton screens and spinners

---

## Responsive Design

**Breakpoints (Tailwind):**
- `sm`: 640px
- `md`: 768px
- `lg`: 1024px
- `xl`: 1280px
- `2xl`: 1536px

**Strategy:**
- Mobile-first approach
- Responsive grid layouts
- Adaptive navigation
- Touch-friendly interactions

---

## API Contract with Backend

**Base URL:** `http://localhost:8080`
**Content-Type:** `application/json`
**CORS:** Enabled for localhost development

**Key Endpoints Used:**
1. `POST /v1/store` - Memory ingestion
2. `GET /v1/retrieve` - Memory search
3. `POST /v1/retrieve/structured` - Categorized retrieval
4. `GET /health/full` - Service health

---

## Development Workflow

**Local Development:**
1. Start backend API: `./run_docker.sh` or `uvicorn src.app:app --reload`
2. Start UI dev server: `cd ui && npm run dev`
3. Access UI: `http://localhost:5173`

**Production Build:**
1. Build UI: `cd ui && npm run build`
2. Output: `ui/dist/`
3. Served via Docker: `http://localhost:80`

---

## Deployment

**Docker Container:**
- Nginx serving static build
- Port: 80
- Volume: `ui/dist` mounted as static files
- Environment: Production optimized

**docker-compose.yml:**
```yaml
ui:
  build:
    context: ./ui
  ports:
    - "80:80"
  volumes:
    - ./ui/dist:/usr/share/nginx/html
```

---

## Future Enhancements

### Potential Components
- Portfolio dashboard (charts for holdings)
- Narrative timeline visualization
- Emotional pattern graphs
- Skill progression trees
- Real-time memory injection display (for orchestrator)

### Potential Libraries
- Chart.js or Recharts for data visualization
- React Hook Form for complex forms
- Zod for runtime validation
- date-fns for date manipulation

---

## Accessibility

**Standards:** WCAG 2.1 Level AA
**Features (via Radix UI):**
- Keyboard navigation
- Screen reader support
- Focus management
- ARIA attributes

---

## Performance Optimizations

**Implemented:**
- Code splitting with React.lazy
- TanStack Query caching
- Vite build optimizations
- Static asset optimization

**Metrics:**
- Initial load: <2s
- Time to Interactive: <3s
- Lighthouse score: Target 90+
