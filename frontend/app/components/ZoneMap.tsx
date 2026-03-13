"use client";

import { useEffect } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from "react-leaflet";
import { useRouter } from "next/navigation";
import "leaflet/dist/leaflet.css";

// ─── Types ────────────────────────────────────────────────────────────────────

type Zone = {
  zone_id:     string;
  zone_name:   string;
  urban_score: number;
  level:       string;
  top_causes:  string[];
};

type Props = {
  zones: Zone[];
};

// ─── Centroïdes — alignés sur backend/services/ingestion.py ──────────────────

const CENTROIDS: Record<string, [number, number]> = {
  "part-dieu":    [45.7605, 4.8597],
  "presquile":    [45.7640, 4.8330],
  "vieux-lyon":   [45.7620, 4.8270],
  "perrache":     [45.7490, 4.8280],
  "gerland":      [45.7330, 4.8330],
  "guillotiere":  [45.7530, 4.8450],
  "brotteaux":    [45.7650, 4.8680],
  "villette":     [45.7580, 4.8780],
  "montchat":     [45.7540, 4.8900],
  "fourviere":    [45.7620, 4.8200],
  "croix-rousse": [45.7780, 4.8370],
  "confluence":   [45.7430, 4.8210],
};

// ─── Couleur par score ────────────────────────────────────────────────────────

function scoreToColor(score: number): string {
  if (score >= 72) return "#ef4444";
  if (score >= 55) return "#f97316";
  if (score >= 35) return "#eab308";
  return "#22c55e";
}

function scoreToRadius(score: number): number {
  return 18 + (score / 100) * 22;
}

// ─── Cercle pulsant SVG pour les zones TENDU/CRITIQUE ────────────────────────

function PulseMarker({ pos, color, score, zoneId, zoneName, onClick }: {
  pos: [number, number]; color: string; score: number;
  zoneId: string; zoneName: string; onClick: () => void;
}) {
  const { DivIcon, Marker } = require("leaflet");
  const { Marker: RLMarker } = require("react-leaflet");
  const r = scoreToRadius(score);
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
          font-weight:700;font-size:12px;color:${color};
          text-shadow:0 1px 3px #000;
          cursor:pointer;
        ">${score}</span>
      </div>
    `,
  });

  return <RLMarker position={pos} icon={icon} eventHandlers={{ click: onClick }} />;
}

// ─── Fix zoom Leaflet sur resize ─────────────────────────────────────────────

function MapResizer() {
  const map = useMap();
  useEffect(() => {
    setTimeout(() => map.invalidateSize(), 100);
  }, [map]);
  return null;
}

// ─── Composant ────────────────────────────────────────────────────────────────

export default function ZoneMap({ zones }: Props) {
  const router = useRouter();

  return (
    <MapContainer
      center={[45.757, 4.832]}
      zoom={13}
      style={{ height: 420, width: "100%", borderRadius: 12, background: "#13161f" }}
      zoomControl={true}
      attributionControl={false}
      aria-label="Carte interactive des zones urbaines de Lyon"
    >
      <MapResizer />

      {/* Tuiles sombres — CartoDB Dark Matter */}
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://carto.com/">CARTO</a>'
      />

      {zones.map(zone => {
        const pos = CENTROIDS[zone.zone_id];
        if (!pos) return null;
        const color  = scoreToColor(zone.urban_score);
        const radius = scoreToRadius(zone.urban_score);
        const isAlert = zone.urban_score >= 55;

        if (isAlert) {
          return (
            <PulseMarker
              key={zone.zone_id}
              pos={pos}
              color={color}
              score={zone.urban_score}
              zoneId={zone.zone_id}
              zoneName={zone.zone_name}
              onClick={() => router.push(`/zones/${zone.zone_id}`)}
            />
          );
        }

        return (
          <CircleMarker
            key={zone.zone_id}
            center={pos}
            radius={radius}
            pathOptions={{
              color,
              fillColor: color,
              fillOpacity: 0.35,
              weight: 2,
            }}
            eventHandlers={{
              click: () => router.push(`/zones/${zone.zone_id}`),
              mouseover: (e) => e.target.setStyle({ fillOpacity: 0.65 }),
              mouseout:  (e) => e.target.setStyle({ fillOpacity: 0.35 }),
            }}
          >
            <Tooltip
              permanent
              direction="center"
              className="zone-label"
              offset={[0, 0]}
            >
              <span style={{
                fontSize: 11, fontWeight: 700, color,
                textShadow: "0 1px 3px #000", cursor: "pointer",
              }}>
                {zone.urban_score}
              </span>
            </Tooltip>
          </CircleMarker>
        );
      })}

      {/* Animation pulse CSS */}
      <style>{`
        @keyframes pulse {
          0%   { transform: scale(1);   opacity: 0.4; }
          70%  { transform: scale(1.6); opacity: 0;   }
          100% { transform: scale(1.6); opacity: 0;   }
        }
      `}</style>
    </MapContainer>
  );
}