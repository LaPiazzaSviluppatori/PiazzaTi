import React from "react";

type HeaderProps = {
  onLogout?: () => void;
};

const Header: React.FC<HeaderProps> = ({ onLogout }) => {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/60">
      <div className="container flex h-16 items-center justify-between px-4">
        <div className="flex-1" />
        <h1 className="text-pink-700 font-bold uppercase tracking-wide text-xl sm:text-2xl text-center">PIAZZATI</h1>
        <div className="flex-1 flex items-center justify-end">
          {onLogout ? (
            <button
              className="text-sm px-4 py-2 rounded border border-pink-900 bg-pink-900 text-pink-100 hover:bg-pink-800 hover:border-pink-800"
              onClick={onLogout}
              title="Logout"
            >
              Logout
            </button>
          ) : null}
        </div>
      </div>
    </header>
  );
};

export default Header;
