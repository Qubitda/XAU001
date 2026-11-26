import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export type ThemeMode = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

const STORAGE_KEY = 'tara-theme';

type ThemeContextValue = {
  theme: ThemeMode;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function getSystemTheme(): ResolvedTheme {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function readStoredTheme(): ThemeMode {
  if (typeof window === 'undefined') return 'system';
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (raw === 'light' || raw === 'dark' || raw === 'system') return raw;
  return 'system';
}

function applyThemeClass(resolved: ResolvedTheme) {
  const root = document.documentElement;
  root.classList.toggle('dark', resolved === 'dark');
  root.style.colorScheme = resolved;
}

/**
 * Inline this in index.html <head> to prevent FOUC (also exported for docs).
 * Must stay in sync with STORAGE_KEY + class strategy above.
 */
export const THEME_INIT_SCRIPT = `(function(){try{var k=${JSON.stringify(STORAGE_KEY)};var t=localStorage.getItem(k);var d=window.matchMedia('(prefers-color-scheme: dark)').matches;var r=t==='dark'||(t!=='light'&&d)?'dark':'light';var e=document.documentElement;e.classList.toggle('dark',r==='dark');e.style.colorScheme=r;}catch(e){}})();`;

export function ThemeProvider({
  children,
  forcedTheme,
}: {
  children: ReactNode;
  /** B2C vitrin: lock to light — no day/night toggle. */
  forcedTheme?: ResolvedTheme;
}) {
  const [theme, setThemeState] = useState<ThemeMode>(() =>
    forcedTheme ? forcedTheme : readStoredTheme()
  );
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() => {
    if (forcedTheme) return forcedTheme;
    const stored = readStoredTheme();
    return stored === 'system' ? getSystemTheme() : stored;
  });

  const setTheme = useCallback(
    (next: ThemeMode) => {
      if (forcedTheme) return;
      setThemeState(next);
      try {
        window.localStorage.setItem(STORAGE_KEY, next);
      } catch {
        // ignore quota / private mode
      }
    },
    [forcedTheme]
  );

  const toggleTheme = useCallback(() => {
    if (forcedTheme) return;
    setTheme(resolvedTheme === 'dark' ? 'light' : 'dark');
  }, [forcedTheme, resolvedTheme, setTheme]);

  useEffect(() => {
    if (forcedTheme) {
      setThemeState(forcedTheme);
      setResolvedTheme(forcedTheme);
      applyThemeClass(forcedTheme);
      return;
    }
    const resolved = theme === 'system' ? getSystemTheme() : theme;
    setResolvedTheme(resolved);
    applyThemeClass(resolved);
  }, [theme, forcedTheme]);

  useEffect(() => {
    if (forcedTheme || theme !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => {
      const resolved = getSystemTheme();
      setResolvedTheme(resolved);
      applyThemeClass(resolved);
    };
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [theme, forcedTheme]);

  const value = useMemo(
    () => ({ theme: forcedTheme ?? theme, resolvedTheme: forcedTheme ?? resolvedTheme, setTheme, toggleTheme }),
    [forcedTheme, theme, resolvedTheme, setTheme, toggleTheme]
  );

  return createElement(ThemeContext.Provider, { value }, children);
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error('useTheme must be used inside <ThemeProvider>');
  }
  return ctx;
}
