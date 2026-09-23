import { useSyncExternalStore } from 'react';

export type MobileWorkspaceView = 'inbox' | 'detail' | 'search' | 'actions' | 'calendar';

type MobileWorkspaceStore = {
  view: MobileWorkspaceView;
  listeners: Set<() => void>;
};

declare global {
  interface Window {
    __naruonMobileWorkspace?: MobileWorkspaceStore;
  }
}

const serverStore: MobileWorkspaceStore = {
  view: 'inbox',
  listeners: new Set<() => void>(),
};

function getStore(): MobileWorkspaceStore {
  if (typeof window === 'undefined') {
    return serverStore;
  }

  window.__naruonMobileWorkspace ??= {
    view: 'inbox',
    listeners: new Set<() => void>(),
  };

  return window.__naruonMobileWorkspace;
}

function getHashMobileWorkspaceView(): MobileWorkspaceView | null {
  if (typeof window === 'undefined') {
    return null;
  }

  const hashView = window.location.hash.replace(/^#mobile-/, '');
  return hashView === 'inbox' || hashView === 'detail' || hashView === 'search' || hashView === 'actions' || hashView === 'calendar'
    ? hashView
    : null;
}

export function setMobileWorkspaceView(
  view: MobileWorkspaceView,
  options: { updateHash?: boolean } = {},
) {
  const store = getStore();
  store.view = view;
  if (typeof window !== 'undefined') {
    if (options.updateHash ?? true) {
      window.history.pushState(null, '', `#mobile-${view}`);
    }
    window.dispatchEvent(new CustomEvent('naruon:mobile-workspace', { detail: { view } }));
  }
  store.listeners.forEach((listener) => listener());
}

export function useMobileWorkspaceView() {
  return useSyncExternalStore(
    (listener) => {
      const store = getStore();
      store.listeners.add(listener);
      window.addEventListener('hashchange', listener);
      return () => {
        store.listeners.delete(listener);
        window.removeEventListener('hashchange', listener);
      };
    },
    () => getHashMobileWorkspaceView() ?? getStore().view,
    () => 'inbox',
  );
}
