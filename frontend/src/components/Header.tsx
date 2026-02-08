import React from "react";
import { Bell, MessageCircle } from "lucide-react";

type HeaderProps = {
  onLogout?: () => void;
  showInbox?: boolean;
  inboxCount?: number;
  hasUnreadInbox?: boolean;
  onToggleInbox?: () => void;
   showChat?: boolean;
   onToggleChat?: () => void;
};

const Header: React.FC<HeaderProps> = ({
  onLogout,
  showInbox,
  inboxCount = 0,
  hasUnreadInbox,
  onToggleInbox,
  showChat,
  onToggleChat,
}) => {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/60">
      <div className="container flex h-16 items-center justify-between px-4">
        <div className="flex-1" />
        <h1 className="text-pink-700 font-bold uppercase tracking-wide text-xl sm:text-2xl text-center">PIAZZATI</h1>
        <div className="flex-1 flex items-center justify-end gap-3">
          {showChat && (
            <button
              type="button"
              className="relative inline-flex items-center justify-center rounded-full h-9 w-9 border border-pink-900 bg-pink-50 text-pink-900 hover:bg-pink-100 focus:outline-none"
              onClick={onToggleChat}
              title="Chat"
            >
              <MessageCircle className="h-4 w-4" />
            </button>
          )}
          {showInbox && (
            <button
              type="button"
              className="relative inline-flex items-center justify-center rounded-full h-9 w-9 border border-pink-900 bg-pink-50 text-pink-900 hover:bg-pink-100 focus:outline-none"
              onClick={onToggleInbox}
              title="Messaggi ricevuti"
            >
              <Bell className="h-4 w-4" />
              {inboxCount > 0 && (
                <span className={`absolute -top-1 -right-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${hasUnreadInbox ? "bg-red-600 text-white" : "bg-pink-300 text-pink-950"}`}>
                  {inboxCount}
                </span>
              )}
            </button>
          )}
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
