"use client";

import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from "react-leaflet";
import { useRouter } from "next/navigation";
import "leaflet/dist/leaflet.css";
import "./zone-map.css";
import type { ZoneSummary } from "@/domain/types";
import { scoreColor, scoreToRadius } from "@/domain/scoring";
import { ZONE_CENTROIDS } from "@/domain/constants";

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

function PulseMarker({ pos, color, score, radius, onClick }: {
  pos: [number, number]; color: string; score: number; radius: number; onClick: () => void;
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
          background:${color}55;
          border:2px solid ${color};
          display:flex;align-items:center;justify-content:center;
          font-weight:700;font-size:${r < 20 ? 10 : 12}px;color:${color};
          text-shadow:0 1px 3px #000;
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

// ─── Composant ──────────────────────────────────────────────────────────────

export default function ZoneMap({ zones }: Props) {
  const router = useRouter();
  const isMobile = useIsMobile();
  const radiusScale = isMobile ? 0.7 : 1;

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
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://carto.com/">CARTO</a>'
      />

      {zones.map(zone => {
        const pos = ZONE_CENTROIDS[zone.zone_id];
        if (!pos) return null;
        const color  = scoreColor(zone.urban_score);
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
              onClick={() => router.push(`/zones/${zone.zone_id}`)}
            />
          );
        }

        return (
          <CircleMarker
            key={zone.zone_id}
            center={pos}
            radius={radius}
            pathOptions={{ color, fillColor: color, fillOpacity: 0.35, weight: 2 }}
            eventHandlers={{
              click: () => router.push(`/zones/${zone.zone_id}`),
              mouseover: (e) => e.target.setStyle({ fillOpacity: 0.65 }),
              mouseout:  (e) => e.target.setStyle({ fillOpacity: 0.35 }),
            }}
          >
            <Tooltip permanent direction="center" className="zone-label" offset={[0, 0]}>
              <span style={{ fontSize: isMobile ? 9 : 11, fontWeight: 700, color, textShadow: "0 1px 3px #000", cursor: "pointer" }}>
                {zone.urban_score}
              </span>
            </Tooltip>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
