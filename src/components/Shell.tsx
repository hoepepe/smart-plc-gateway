import React, { useEffect, useRef, useState } from 'react';
import { Bell, ChevronDown, Lock, PanelLeft, Plus, Radio, Network, X, CalendarDays, ChevronRight } from 'lucide-react';

/* Khung giao diện kiểu MEXA: thanh bên trắng có nút chính xanh, thanh trên có chuông và người dùng,
   nền xám nhạt, thẻ trắng bo góc. Mọi màn hình nằm trong khung này. */

export interface NavItem {
  id: string; label: string; icon: React.ElementType;
  badge?: { text: string; tone?: 'gray' | 'red' | 'blue' };
}

export interface Notice {
  id: string; title: string; sub: string; tone: 'red' | 'amber' | 'blue'; go: () => void;
}

const BADGE = {
  gray: 'bg-slate-100 text-slate-600',
  red: 'bg-rose-500 text-white',
  blue: 'bg-brand-50 text-brand-700',
};

export function Logo({ small = false }: { small?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="w-8 h-8 rounded-lg bg-brand-600 text-white grid place-items-center shadow-sm shrink-0">
        <Network size={18} strokeWidth={2.4} />
      </span>
      {!small && (
        <span className="leading-none">
          <span className="block text-[17px] font-bold tracking-tight text-slate-900">Smart PLC</span>
          <span className="block text-[10px] font-medium text-slate-500 mt-0.5 tracking-wide">GATEWAY · DENSO D1</span>
        </span>
      )}
    </div>
  );
}

export function Sidebar({ items, active, onNav, onPrimary, collapsed, mobileOpen, onCloseMobile }: {
  items: NavItem[]; active: string; onNav: (id: string) => void; onPrimary: () => void;
  collapsed: boolean; mobileOpen: boolean; onCloseMobile: () => void;
}) {
  const body = (mini: boolean) => (
    <div className="h-full flex flex-col">
      <div className={`h-16 flex items-center ${mini ? 'justify-center' : 'px-6'}`}><Logo small={mini} /></div>
      <div className={mini ? 'px-3' : 'px-4'}>
        <button onClick={onPrimary} title="Thêm máy"
          className={`w-full inline-flex items-center justify-center gap-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium rounded-xl shadow-sm shadow-brand-600/20 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 ${mini ? 'h-11' : 'h-11 px-4'}`}>
          <Plus size={17} />{!mini && 'Thêm máy'}
        </button>
      </div>
      <nav className={`mt-6 flex-1 space-y-1 ${mini ? 'px-3' : 'px-3'}`} aria-label="Các màn hình">
        {items.map((it) => {
          const on = it.id === active;
          const I = it.icon;
          return (
            <button key={it.id} onClick={() => onNav(it.id)} aria-current={on ? 'page' : undefined} title={mini ? it.label : undefined}
              className={`relative w-full flex items-center gap-3 rounded-lg text-sm transition-colors focus-visible:outline-2 focus-visible:outline-brand-600 ${
                mini ? 'justify-center h-11' : 'px-3 h-11'} ${
                on ? 'bg-brand-50 text-brand-700 font-medium' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'}`}>
              {on && <span className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r bg-brand-600" />}
              <I size={18} strokeWidth={on ? 2.2 : 1.8} className="shrink-0" />
              {!mini && <span className="flex-1 text-left truncate">{it.label}</span>}
              {it.badge && !mini && (
                <span className={`text-[11px] font-medium rounded-full px-2 py-0.5 tabular-nums ${BADGE[it.badge.tone ?? 'gray']}`}>{it.badge.text}</span>
              )}
              {it.badge && mini && it.badge.tone === 'red' && <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-rose-500" />}
            </button>
          );
        })}
      </nav>
      <div className={`border-t border-slate-100 ${mini ? 'p-3 flex justify-center' : 'p-4'}`}>
        <div className="flex items-center gap-3">
          <span className="w-9 h-9 rounded-full bg-[#c9958a] text-white text-xs font-semibold grid place-items-center shrink-0">UB</span>
          {!mini && (
            <div className="min-w-0">
              <div className="text-sm font-semibold text-slate-900 truncate">UET-BigHero</div>
              <div className="text-[11px] text-slate-500 truncate">DENSO Factory Hacks 2026</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
  return (
    <>
      <aside className={`hidden lg:block fixed inset-y-0 left-0 z-30 bg-white border-r border-slate-200/80 transition-[width] duration-200 ${collapsed ? 'w-[76px]' : 'w-64'}`}>
        {body(collapsed)}
      </aside>
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="absolute inset-0 bg-slate-900/30" onClick={onCloseMobile} />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85vw] bg-white shadow-xl">
            <button onClick={onCloseMobile} aria-label="Đóng menu" className="absolute top-4 right-3 p-1.5 text-slate-400 hover:text-slate-700"><X size={18} /></button>
            {body(false)}
          </aside>
        </div>
      )}
    </>
  );
}

export function Topbar({ title, onToggle, clock, live, connLabel, connTitle, notices }: {
  title: string; onToggle: () => void; clock: string; live: boolean; connLabel: string; connTitle: string; notices: Notice[];
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', h); document.addEventListener('keydown', k);
    return () => { document.removeEventListener('mousedown', h); document.removeEventListener('keydown', k); };
  }, [open]);
  const DOT = { red: 'bg-rose-500', amber: 'bg-amber-500', blue: 'bg-brand-500' };
  return (
    <header className="sticky top-0 z-20 h-16 bg-white/90 backdrop-blur border-b border-slate-200/80">
      <div className="h-full px-4 sm:px-6 flex items-center gap-3">
        <button onClick={onToggle} aria-label="Ẩn hoặc hiện thanh bên" className="p-2 -ml-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800">
          <PanelLeft size={19} />
        </button>
        <h1 className="text-[15px] font-semibold text-slate-900 truncate">{title}</h1>
        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          <span className="hidden md:inline font-mono text-xs text-slate-500 tabular-nums">{clock}</span>
          <span className="hidden sm:inline-flex items-center gap-1.5 text-xs text-slate-600 border border-slate-200 rounded-full px-2.5 py-1"
            title="Gateway chỉ gửi lệnh đọc, không có lệnh ghi nào tới PLC"><Lock size={12} /> Chỉ đọc</span>
          <span title={connTitle} className={`inline-flex items-center gap-1.5 text-xs rounded-full px-2.5 py-1 border ${
            live ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-slate-50 text-slate-600 border-slate-200'}`}>
            <Radio size={12} /><span className="hidden sm:inline">{connLabel}</span>
          </span>
          <div className="relative" ref={ref}>
            <button onClick={() => setOpen((v) => !v)} aria-label={`Thông báo (${notices.length})`} aria-expanded={open}
              className="relative p-2 rounded-lg text-slate-600 hover:bg-slate-100">
              <Bell size={19} />
              {notices.length > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-brand-600 text-white text-[10px] font-semibold grid place-items-center tabular-nums">
                  {notices.length > 9 ? '9+' : notices.length}
                </span>
              )}
            </button>
            {open && (
              <div className="absolute right-0 mt-2 w-[340px] max-w-[calc(100vw-2rem)] bg-white border border-slate-200 rounded-xl shadow-xl overflow-hidden">
                <div className="px-4 py-3 flex items-center justify-between border-b border-slate-100">
                  <span className="text-sm font-semibold text-slate-900">Thông báo</span>
                  {notices.length > 0 && <span className="text-[11px] font-medium bg-brand-600 text-white rounded-full px-2 py-0.5">{notices.length} mới</span>}
                </div>
                {notices.length === 0 ? (
                  <p className="px-4 py-6 text-sm text-slate-500 text-center">Không có gì cần chú ý.</p>
                ) : (
                  <ul className="max-h-80 overflow-y-auto divide-y divide-slate-100">
                    {notices.map((n) => (
                      <li key={n.id}>
                        <button onClick={() => { n.go(); setOpen(false); }} className="w-full text-left px-4 py-3 flex gap-3 hover:bg-slate-50">
                          <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${DOT[n.tone]}`} />
                          <span className="min-w-0 flex-1">
                            <span className="block text-sm text-slate-900">{n.title}</span>
                            <span className="block text-xs text-slate-500 mt-0.5">{n.sub}</span>
                          </span>
                          <ChevronRight size={15} className="text-slate-300 mt-1 shrink-0" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
          <div className="hidden sm:flex items-center gap-2.5 pl-3 border-l border-slate-200">
            <span className="w-9 h-9 rounded-full bg-brand-600 text-white text-sm font-semibold grid place-items-center">01</span>
            <span className="leading-tight hidden md:block">
              <span className="block text-sm font-semibold text-slate-900">Gateway 01</span>
              <span className="block text-[11px] text-slate-500">Line 2 · UET-BigHero</span>
            </span>
            <ChevronDown size={15} className="text-slate-400 hidden md:block" />
          </div>
        </div>
      </div>
    </header>
  );
}

export function PageHeader({ title, sub, right }: { title: React.ReactNode; sub?: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
      <div className="min-w-0">
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h2>
        {sub && <p className="text-sm text-slate-500 mt-1">{sub}</p>}
      </div>
      {right && <div className="flex flex-wrap items-center gap-2">{right}</div>}
    </div>
  );
}

export function DateChip() {
  const d = new Date().toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
  return (
    <span className="inline-flex items-center gap-2 h-10 px-3.5 text-sm text-slate-700 bg-white border border-slate-200 rounded-xl">
      <CalendarDays size={15} className="text-slate-400" />{d}
    </span>
  );
}

export function PrimaryButton({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className="inline-flex items-center gap-2 h-10 px-4 text-sm font-medium text-white bg-brand-600 hover:bg-brand-700 rounded-xl shadow-sm shadow-brand-600/20 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600">
      {children}
    </button>
  );
}

/* Thẻ chỉ số kiểu MEXA: nhãn nhỏ, số lớn, ô biểu tượng màu ở góc phải, dòng phụ màu. */
export function KpiCard({ label, value, icon: I, tone = 'blue', foot, footTone = 'blue', onClick }: {
  label: string; value: React.ReactNode; icon: React.ElementType; tone?: 'blue' | 'amber' | 'emerald' | 'rose';
  foot?: React.ReactNode; footTone?: 'blue' | 'amber' | 'emerald' | 'rose' | 'slate'; onClick?: () => void;
}) {
  const chip = { blue: 'bg-brand-50 text-brand-600', amber: 'bg-amber-50 text-amber-600', emerald: 'bg-emerald-50 text-emerald-600', rose: 'bg-rose-50 text-rose-600' }[tone];
  const ft = { blue: 'text-brand-600', amber: 'text-amber-600', emerald: 'text-emerald-600', rose: 'text-rose-600', slate: 'text-slate-500' }[footTone];
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag onClick={onClick} className={`text-left bg-white border border-slate-200/80 rounded-xl shadow-card p-5 ${onClick ? 'hover:border-brand-200 transition-colors' : ''}`}>
      <div className="flex items-start justify-between gap-3">
        <span className="text-sm font-medium text-slate-700">{label}</span>
        <span className={`w-8 h-8 rounded-lg grid place-items-center shrink-0 ${chip}`}><I size={16} /></span>
      </div>
      <div className="mt-2 text-[28px] leading-none font-bold text-slate-900 tabular-nums">{value}</div>
      {foot && <div className={`mt-3 text-xs ${ft}`}>{foot}</div>}
    </Tag>
  );
}
