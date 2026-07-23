"use client";

import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";

export type Place = {
  id: number;
  name: string;
  address: string;
  prefecture: string;
  category: string;
  toilet_score: number | null;
  confidence: number | null;
  latitude: number;
  longitude: number;
};

const icon = new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

export default function MapView({ places }: { places: Place[] }) {
  const center: [number, number] = places.length
    ? [places[0].latitude, places[0].longitude]
    : [36.2048, 138.2529];

  return (
    <div className="map">
      <MapContainer center={center} zoom={places.length ? 12 : 5} scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {places.map((place) => (
          <Marker key={place.id} position={[place.latitude, place.longitude]} icon={icon}>
            <Popup>
              <strong>{place.name}</strong>
              <br />
              {place.address}
              <br />
              きれい度: {place.toilet_score == null ? "未評価" : `${place.toilet_score}点`}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
