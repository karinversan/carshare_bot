// -------------------------------------------------------------------------- //
//                                    TYPES                                   //
// -------------------------------------------------------------------------- //

type TelegramUnsafeUser = {
  first_name?: string;
  username?: string;
};

type TelegramInitDataUnsafe = {
  user?: TelegramUnsafeUser;
} & Record<string, unknown>;

export type TelegramWebApp = {
  MainButton: {
    hide: () => void;
    hideProgress: () => void;
    offClick: (cb: () => void) => void;
    onClick: (cb: () => void) => void;
    show: () => void;
    showProgress: (leaveActive?: boolean) => void;
    text: string;
  };
  close: () => void;
  expand: () => void;
  initData: string;
  initDataUnsafe: TelegramInitDataUnsafe;
  ready: () => void;
  sendData: (value: string) => void;
};

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }
}

// -------------------------------------------------------------------------- //
//                                   EXPORTS                                  //
// -------------------------------------------------------------------------- //

export const tg = window.Telegram?.WebApp;
