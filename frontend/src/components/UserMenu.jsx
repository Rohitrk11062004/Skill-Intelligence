import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    const onDocMouseDown = (e) => {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDocMouseDown);
    return () => document.removeEventListener('mousedown', onDocMouseDown);
  }, []);

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        className="w-10 h-10 rounded-full border-2 border-primary/20 bg-surface flex items-center justify-center"
        onClick={() => setOpen((v) => !v)}
        aria-label="Open user menu"
      >
        <span className="material-symbols-outlined text-white">person</span>
      </button>

      {open && (
        <div className="absolute right-0 mt-3 w-56 rounded-xl border border-outline-variant/20 bg-surface-container shadow-xl overflow-hidden z-50">
          <div className="px-4 py-3 border-b border-outline-variant/10">
            <p className="text-sm font-medium text-white truncate">
              {user?.full_name || user?.username || 'User'}
            </p>
            <p className="text-xs text-on-surface-variant truncate">{user?.email || ''}</p>
          </div>
          <div className="py-1">
            <Link
              to="/profile"
              className="block px-4 py-2 text-sm text-on-surface-variant hover:text-white hover:bg-surface-container-highest"
              onClick={() => setOpen(false)}
            >
              Info
            </Link>
            <Link
              to="/settings"
              className="block px-4 py-2 text-sm text-on-surface-variant hover:text-white hover:bg-surface-container-highest"
              onClick={() => setOpen(false)}
            >
              Settings
            </Link>
            <Link
              to="/assessments-summary"
              className="block px-4 py-2 text-sm text-on-surface-variant hover:text-white hover:bg-surface-container-highest"
              onClick={() => setOpen(false)}
            >
              Assessment results
            </Link>
          </div>
          <div className="border-t border-outline-variant/10">
            <button
              type="button"
              className="w-full text-left px-4 py-2 text-sm text-error hover:bg-error/10"
              onClick={() => {
                setOpen(false);
                logout();
                navigate('/login');
              }}
            >
              Logout
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

