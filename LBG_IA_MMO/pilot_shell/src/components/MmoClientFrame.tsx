import { useMemo } from "react";
import { mmoClientUrl } from "../lib/urls";

type MmoClientFrameProps = {
  className?: string;
};

export function MmoClientFrame({ className }: MmoClientFrameProps) {
  const src = useMemo(() => mmoClientUrl(), []);

  return (
    <div className={`mmo-frame${className ? ` ${className}` : ""}`}>
      <iframe
        className="mmo-frame__iframe"
        title="Client MMO — Core3 Prime"
        src={src}
        allow="fullscreen"
        referrerPolicy="no-referrer-when-downgrade"
      />
      <footer className="mmo-frame__bar">
        <span className="muted">{src}</span>
        <a className="muted-link" href={src} target="_blank" rel="noopener noreferrer">
          Ouvrir dans un onglet
        </a>
      </footer>
    </div>
  );
}
