import { useCallback, useEffect, useState } from 'react';
import { Bell } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../../../components/ui/dropdown-menu';
import { apiFetch } from '../../../lib/api/client';

type NotifItem = {
  id: string;
  title: string;
  body: string;
  isRead: boolean;
  createdAt: string;
};

type NotifPayload = {
  unreadCount: number;
  items: NotifItem[];
};

export function StorefrontNotificationBell() {
  const [unread, setUnread] = useState(0);
  const [items, setItems] = useState<NotifItem[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch<NotifPayload>('/api/v1/storefront/notifications');
      setUnread(res.data?.unreadCount ?? 0);
      setItems(res.data?.items ?? []);
    } catch {
      setUnread(0);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 60_000);
    return () => window.clearInterval(id);
  }, [load]);

  const markRead = async (id: string) => {
    try {
      await apiFetch(`/api/v1/storefront/notifications/${id}`, {
        method: 'PATCH',
        body: { isRead: true },
      });
      await load();
    } catch {
      // ignore
    }
  };

  const markAll = async () => {
    try {
      await apiFetch('/api/v1/storefront/notifications/read-all', { method: 'POST' });
      await load();
    } catch {
      // ignore
    }
  };

  return (
    <DropdownMenu
      onOpenChange={(open) => {
        if (open) void load();
      }}
    >
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={unread > 0 ? `Bildirimler (${unread} okunmamış)` : 'Bildirimler'}
          className="relative inline-flex items-center justify-center w-10 h-10 rounded-full text-foreground hover:bg-border/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors cursor-pointer"
        >
          <Bell className="w-[19px] h-[19px] stroke-[1.6]" />
          {unread > 0 && (
            <span className="absolute top-1 right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-primary text-white font-mono text-[10px] font-semibold leading-4 text-center tabular-nums">
              {unread > 9 ? '9+' : unread}
            </span>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" sideOffset={8} className="w-80 bg-card border-border shadow-md">
        <DropdownMenuLabel className="flex items-center justify-between gap-2">
          <span>Bildirimler</span>
          {unread > 0 ? (
            <button
              type="button"
              onClick={() => void markAll()}
              className="text-[11px] font-medium text-muted-foreground hover:text-foreground"
            >
              Tümünü okundu
            </button>
          ) : null}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {loading && items.length === 0 ? (
          <div className="px-3 py-4 text-xs text-muted-foreground">Yükleniyor…</div>
        ) : items.length === 0 ? (
          <div className="px-3 py-4 text-xs text-muted-foreground">Bildirim yok.</div>
        ) : (
          items.slice(0, 8).map((n) => (
            <DropdownMenuItem
              key={n.id}
              className="flex flex-col items-start gap-0.5 py-2.5 cursor-pointer"
              onSelect={() => {
                if (!n.isRead) void markRead(n.id);
              }}
            >
              <span
                className={`text-xs ${n.isRead ? 'text-muted-foreground' : 'font-semibold text-foreground'}`}
              >
                {n.title}
              </span>
              <span className="text-[11px] text-muted-foreground line-clamp-2">{n.body}</span>
            </DropdownMenuItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
