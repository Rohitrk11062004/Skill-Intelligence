import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import UserMenu from './UserMenu';

const baseLink =
  'text-[#a7aab9] hover:text-white hover:bg-[#272c39]/40 rounded-lg px-3 py-1 transition-all duration-300';
const activeLink = 'text-[#699cff] border-b border-[#699cff] pb-1 transition-all duration-300';

export default function AppHeader() {
  const { user } = useAuth();
  const isManager = !!user?.is_manager;

  const leftNav = isManager
    ? [
        { key: 'admin', href: '/admin', label: 'Admin' },
        { key: 'jds', href: '/jds', label: 'Upload JDs' },
        { key: 'taxonomy', href: '/taxonomy', label: 'Skill Taxonomy' },
      ]
    : [
        { key: 'dashboard', href: '/dashboard', label: 'Dashboard' },
        { key: 'skill-analysis', href: '/skill-analysis', label: 'Skill Analysis' },
        { key: 'learning', href: '/learning', label: 'Learning' },
        { key: 'assessments', href: '/assessments-summary', label: 'Assessments' },
      ];

  return (
    <header className="fixed top-0 w-full z-50 bg-[#0c0e14]/80 backdrop-blur-lg shadow-[0_20px_50px_rgba(67,136,253,0.05)] bg-gradient-to-b from-[#11131a] to-transparent">
      <div className="flex items-center justify-between px-6 md:px-10 h-20 w-full max-w-[1600px] mx-auto">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-primary to-primary-container rounded-lg flex items-center justify-center">
              <span
                className="material-symbols-outlined text-on-primary-container text-xl"
                style={{ fontVariationSettings: '"FILL" 1' }}
              >
                lens_blur
              </span>
            </div>
            <div className="flex flex-col leading-tight">
              <span className="text-lg font-bold tracking-tighter text-white font-headline">
                Elevate AI
              </span>
              <span className="text-[10px] sm:text-xs text-[#a7aab9] font-normal tracking-tight normal-case mt-0.5 max-w-[220px] sm:max-w-none">
                AI learning and development by ParadigmIT
              </span>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-6 font-['Inter'] font-medium tracking-tight text-sm">
            {leftNav.map((item) => (
              <NavLink
                key={item.key}
                to={item.href}
                end={item.href === '/dashboard' || item.href === '/admin'}
                className={({ isActive }) => (isActive ? activeLink : baseLink)}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3 pl-4 border-l border-outline-variant/30">
            <UserMenu />
          </div>
        </div>
      </div>
    </header>
  );
}

