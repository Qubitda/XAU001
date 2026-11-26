import { Monitor, Moon, Sun } from 'lucide-react';
import { useTheme, type ThemeMode } from '../../providers/ThemeProvider';
import { Button } from './button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './dropdown-menu';
import { cn } from '../../lib/utils';

const OPTIONS: { value: ThemeMode; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Açık', icon: Sun },
  { value: 'dark', label: 'Koyu', icon: Moon },
  { value: 'system', label: 'Sistem', icon: Monitor },
];

export function ThemeToggle({
  className,
  compact = false,
}: {
  className?: string;
  /** Icon-only control for dense headers */
  compact?: boolean;
}) {
  const { theme, resolvedTheme, setTheme, toggleTheme } = useTheme();

  if (compact) {
    return (
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className={cn('relative h-9 w-9', className)}
        onClick={toggleTheme}
        aria-label={resolvedTheme === 'dark' ? 'Açık temaya geç' : 'Koyu temaya geç'}
        title={resolvedTheme === 'dark' ? 'Açık tema' : 'Koyu tema'}
      >
        <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
        <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
      </Button>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className={cn('gap-2', className)}
          aria-label="Tema seçimi"
        >
          <Sun className="h-3.5 w-3.5 dark:hidden" />
          <Moon className="hidden h-3.5 w-3.5 dark:inline" />
          <span className="hidden sm:inline">Tema</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[9rem]">
        {OPTIONS.map(({ value, label, icon: Icon }) => (
          <DropdownMenuItem
            key={value}
            onClick={() => setTheme(value)}
            className={cn(theme === value && 'bg-accent font-medium')}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
