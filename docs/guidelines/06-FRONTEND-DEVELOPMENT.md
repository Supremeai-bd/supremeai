# গাইডলাইন ০৬ — Frontend ডেভেলপমেন্ট

> **স্তর:** নতুন থেকে অভিজ্ঞ React ডেভেলপার
> **প্রযোজ্য:** React/TypeScript, Vite, Vitest

---

## ৬.১ — Component Architecture

```
src/
├── components/          ← reusable UI (Button, Modal, Input)
│   └── Button/
│       ├── Button.tsx
│       ├── Button.test.tsx    ← component-এর পাশে
│       └── index.ts           ← re-export
├── features/            ← business feature (Auth, Dashboard)
│   └── auth/
│       ├── LoginForm.tsx
│       ├── LoginForm.test.tsx
│       ├── useAuth.ts         ← custom hook
│       └── authApi.ts         ← API calls
├── hooks/               ← shared custom hooks
├── lib/                 ← utilities, helpers
├── pages/               ← route-level components (thin)
└── types/               ← TypeScript type definitions
```

---

## ৬.২ — Component লেখার নিয়ম

```typescript
// ✅ CORRECT — typed props, single responsibility
interface ButtonProps {
  label: string
  onClick: () => void
  variant?: 'primary' | 'secondary' | 'danger'
  disabled?: boolean
  isLoading?: boolean
}

export function Button({
  label,
  onClick,
  variant = 'primary',
  disabled = false,
  isLoading = false,
}: ButtonProps) {
  return (
    <button
      className={`btn btn-${variant}`}
      onClick={onClick}
      disabled={disabled || isLoading}
      data-testid="button"   // ← testid যোগ করুন
    >
      {isLoading ? <Spinner size="sm" /> : label}
    </button>
  )
}
```

```typescript
// ❌ WRONG — untyped, does too many things
function Button(props: any) {
  // API call, state, UI — সব এক জায়গায়
  const [data, setData] = useState()
  useEffect(() => { fetch('/api/data').then(...) }, [])
  return <button onClick={props.fn}>{props.txt}</button>
}
```

---

## ৬.৩ — State Management

```typescript
// Local state — component নিজের জন্য
const [isOpen, setIsOpen] = useState(false)

// Server state — TanStack Query ব্যবহার করুন
import { useQuery, useMutation } from '@tanstack/react-query'

function UserProfile({ userId }: { userId: string }) {
  const { data: user, isLoading, error } = useQuery({
    queryKey: ['user', userId],
    queryFn: () => fetchUser(userId),
    staleTime: 5 * 60 * 1000,  // 5 মিনিট fresh
  })

  const updateMutation = useMutation({
    mutationFn: updateUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user', userId] })
    },
  })

  if (isLoading) return <Skeleton />
  if (error) return <ErrorMessage error={error} />

  return <div>{user.name}</div>
}

// Global UI state — Zustand (Redux-এর চেয়ে সহজ)
import { create } from 'zustand'

interface AppStore {
  theme: 'light' | 'dark'
  setTheme: (theme: 'light' | 'dark') => void
}

export const useAppStore = create<AppStore>((set) => ({
  theme: 'light',
  setTheme: (theme) => set({ theme }),
}))
```

---

## ৬.৪ — API Client

```typescript
// src/lib/apiClient.ts — একটাই API client
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080'

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem('access_token')

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
  })

  if (response.status === 401) {
    // token expired — redirect to login
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new ApiError(response.status, error.detail || 'Request failed')
  }

  return response.json()
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
```

---

## ৬.৫ — TypeScript — সঠিক ব্যবহার

```typescript
// ❌ WRONG — any ব্যবহার
function processUser(user: any) {
  return user.name  // typo হলে runtime error
}

// ✅ CORRECT — explicit types
interface User {
  id: string
  name: string
  email: string
  role: 'admin' | 'user'
  createdAt: Date
}

function processUser(user: User): string {
  return user.name  // compile-time check
}

// API response type
interface ApiResponse<T> {
  data: T
  message?: string
  status: 'success' | 'error'
}

// Utility types ব্যবহার করুন
type CreateUserInput = Omit<User, 'id' | 'createdAt'>
type UpdateUserInput = Partial<Pick<User, 'name' | 'email'>>
```

---

## ৬.৬ — Environment Variables (Frontend)

```typescript
// .env.development
VITE_API_URL=http://localhost:8080
VITE_APP_ENV=development

// .env.production
VITE_API_URL=https://api.supremeai.com
VITE_APP_ENV=production
```

```typescript
// src/lib/env.ts — type-safe env access
interface Env {
  VITE_API_URL: string
  VITE_APP_ENV: 'development' | 'production'
}

// Vite-এ import.meta.env ব্যবহার করুন
export const env = {
  apiUrl: import.meta.env.VITE_API_URL,
  isDev: import.meta.env.VITE_APP_ENV === 'development',
} as const
```

**নিয়ম:**
- `VITE_` prefix ছাড়া variable browser-এ expose হয় না
- Secret API key frontend-এ রাখবেন না — backend-এর মাধ্যমে call করুন

---

## ৬.৭ — Vitest টেস্ট

```typescript
// Button.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect } from 'vitest'
import { Button } from './Button'

describe('Button', () => {
  it('renders with label', () => {
    render(<Button label="Click me" onClick={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument()
  })

  it('calls onClick when clicked', async () => {
    const user = userEvent.setup()
    const handleClick = vi.fn()

    render(<Button label="Submit" onClick={handleClick} />)
    await user.click(screen.getByRole('button'))

    expect(handleClick).toHaveBeenCalledOnce()
  })

  it('shows spinner when loading', () => {
    render(<Button label="Submit" onClick={vi.fn()} isLoading />)
    expect(screen.getByRole('button')).toBeDisabled()
    expect(screen.getByTestId('spinner')).toBeInTheDocument()
  })

  it('is disabled when disabled prop is true', () => {
    render(<Button label="Submit" onClick={vi.fn()} disabled />)
    expect(screen.getByRole('button')).toBeDisabled()
  })
})
```

### API Mock pattern

```typescript
// API call টেস্টে mock করুন
import { vi } from 'vitest'
import * as apiClient from '@/lib/apiClient'

vi.mock('@/lib/apiClient')

it('loads user data on mount', async () => {
  vi.mocked(apiClient.apiClient.get).mockResolvedValue({
    id: '123',
    name: 'Test User',
    email: 'test@example.com',
    role: 'user',
  })

  render(<UserProfile userId="123" />)

  await screen.findByText('Test User')
  expect(apiClient.apiClient.get).toHaveBeenCalledWith('/users/123')
})
```

---

## ৬.৮ — Performance

```typescript
// ভারী component lazy load করুন
const HeavyChart = lazy(() => import('./HeavyChart'))

function Dashboard() {
  return (
    <Suspense fallback={<Skeleton />}>
      <HeavyChart />
    </Suspense>
  )
}

// Expensive calculation memo করুন
const sortedUsers = useMemo(
  () => users.sort((a, b) => a.name.localeCompare(b.name)),
  [users]
)

// Callback memo করুন (child component re-render আটকাতে)
const handleDelete = useCallback(
  (id: string) => deleteUser(id),
  [deleteUser]
)
```

---

## চেকলিস্ট — নতুন Component/Feature

- [ ] Props interface TypeScript দিয়ে typed
- [ ] Server state TanStack Query দিয়ে
- [ ] API call `apiClient` দিয়ে, সরাসরি `fetch` নয়
- [ ] `data-testid` attribute আছে (testing-এর জন্য)
- [ ] Test file component-এর পাশে (`Component.test.tsx`)
- [ ] `any` type ব্যবহার করা হয়নি
- [ ] Secret API key frontend code-এ নেই
- [ ] লোডিং + error state handle করা আছে
