"use client";

import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from "react-leaflet";
import { useRouter } from "next/navigation";
import "leaflet/dist/leaflet.css";
import "./zone-map.css";
import type { ZoneSummary } from "@/domain/types";
import { scoreColor, scoreToRadius } from "@/domain/scoring";
import { ZONE_CENTROIDS } from "@/domain/constants";
import { useTheme } from "@/components/theme/ThemeProvider";

type Props = {
  zones: ZoneSummary[];
};

// ─── Responsive scaling ─────────────────────────────────────────────────────

function useIsMobile() {
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 480px)");
    setMobile(mq.matches);
    const handler = (e: MediaQueryListEvent) => setMobile(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return mobile;
}

// ─── Cercle pulsant pour les zones TENDU/CRITIQUE ───────────────────────────

function PulseMarker({ pos, color, score, radius, onClick, fg }: {
  pos: [number, number]; color: string; score: number; radius: number; onClick: () => void; fg: string;
}) {
  const { DivIcon } = require("leaflet");
  const { Marker: RLMarker } = require("react-leaflet");
  const r = radius;
  const size = r * 2 + 20;

  const icon = new DivIcon({
    className: "",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `
      <div style="position:relative;width:${size}px;height:${size}px;display:flex;align-items:center;justify-content:center;">
        <span style="
          position:absolute;
          width:${r * 2}px;height:${r * 2}px;
          border-radius:50%;
          background:${color};
          opacity:0.25;
          animation:pulse 1.8s ease-out infinite;
        "></span>
        <span style="
          position:absolute;
          width:${r * 2 + 10}px;height:${r * 2 + 10}px;
          border-radius:50%;
          background:${color};
          opacity:0.12;
          animation:pulse 1.8s ease-out infinite 0.4s;
        "></span>
        <span style="
          position:relative;
          width:${r * 2}px;height:${r * 2}px;
          border-radius:50%;
          background:${color}77;
          border:2px solid ${color};
          box-shadow:0 1px 3px rgba(0,0,0,0.3);
          display:flex;align-items:center;justify-content:center;
          font-weight:800;font-size:${r < 20 ? 10 : 12}px;color:${fg};
          cursor:pointer;
        ">${score}</span>
      </div>
    `,
  });

  return <RLMarker position={pos} icon={icon} eventHandlers={{ click: onClick }} />;
}

// ─── Fix zoom Leaflet sur resize ────────────────────────────────────────────

function MapResizer() {
  const map = useMap();
  useEffect(() => {
    setTimeout(() => map.invalidateSize(), 100);
  }, [map]);
  return null;
}

// ─── Assombrir une couleur hex de `amount` (0–1) ────────────────────────────

function darkenHex(hex: string, amount: number): string {
  const n = parseInt(hex.slice(1), 16);
  const r = Math.max(0, Math.round(((n >> 16) & 0xff) * (1 - amount)));
  const g = Math.max(0, Math.round(((n >> 8) & 0xff) * (1 - amount)));
  const b = Math.max(0, Math.round((n & 0xff) * (1 - amount)));
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, "0")}`;
}

// ─── Composant ──────────────────────────────────────────────────────────────

export default function ZoneMap({ zones }: Props) {
  const router = useRouter();
  const isMobile = useIsMobile();
  const { resolved } = useTheme();
  const isLight = resolved === "light";
  const radiusScale = isMobile ? 0.7 : 1;
  const tileVariant = isLight ? "light_all" : "dark_all";

  return (
    <MapContainer
      center={[45.757, 4.832]}
      zoom={isMobile ? 12 : 13}
      className="zone-map-container"
      zoomControl={!isMobile}
      attributionControl={false}
      aria-label="Carte interactive des zones urbaines de Lyon"
    >
      <MapResizer />

      <TileLayer
        key={tileVariant}
        url={`https://{s}.basemaps.cartocdn.com/${tileVariant}/{z}/{x}/{y}{r}.png`}
        attribution='&copy; <a href="https://carto.com/">CARTO</a>'
      />

      {zones.map(zone => {
        const pos = ZONE_CENTROIDS[zone.zone_id];
        if (!pos) return null;
        const color  = scoreColor(zone.urban_score);
        const scoreFg = isLight ? darkenHex(color, 0.5) : "#fff";

        const radius = Math.round(scoreToRadius(zone.urban_score) * radiusScale);
        const isAlert = zone.urban_score >= 55;

        if (isAlert) {
          return (
            <PulseMarker
              key={zone.zone_id}
              pos={pos}
              color={color}
              score={zone.urban_score}
              radius={radius}
              fg={scoreFg}
              onClick={() => router.push(`/zones/${zone.zone_id}`)}
            />
          );
        }

        return (
          <CircleMarker
            key={zone.zone_id}
            center={pos}
            radius={radius}
            pathOptions={{ color, fillColor: color, fillOpacity: 0.6, weight: 2 }}
            eventHandlers={{
              click: () => router.push(`/zones/${zone.zone_id}`),
              mouseover: (e) => e.target.setStyle({ fillOpacity: 0.8 }),
              mouseout:  (e) => e.target.setStyle({ fillOpacity: 0.6 }),
            }}
          >
            <Tooltip permanent direction="center" className="zone-label" offset={[0, 0]}>
              <span style={{
                fontSize: isMobile ? 9 : 11,
                fontWeight: 800,
                color: scoreFg,
                cursor: "pointer",
              }}>
                {zone.urban_score}
              </span>
            </Tooltip>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
