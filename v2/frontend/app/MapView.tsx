// Leaflet map for facilities and the optional current user position.
"use client";

import L from "leaflet";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import type { Place, UserLocation } from "./types";

const placeIcon = new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

const userIcon = L.divIcon({
  className: "user-location-marker",
  html: '<span aria-label="現在地"></span>',
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

export default function MapView({
  places,
  userLocation,
}: {
  places: Place[];
  userLocation: UserLocation | null;
}) {
  const center: [number, number] = userLocation
    ? [userLocation.latitude, userLocation.longitude]
    : places.length
      ? [places[0].latitude, places[0].longitude]
      : [36.2048, 138.2529];
  return (
    <div className="map">
      <MapContainer key={`${center[0]}:${center[1]}`} center={center} zoom={places.length ? 13 : 5} scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {userLocation && (
          <Marker position={[userLocation.latitude, userLocation.longitude]} icon={userIcon}>
            <Popup>現在地</Popup>
          </Marker>
        )}
        {places.map((place) => (
          <Marker key={place.id} position={[place.latitude, place.longitude]} icon={placeIcon}>
            <Popup>
              <strong>{place.name}</strong><br />
              {place.address}<br />
              きれい度: {place.toilet_score == null ? "未評価" : `${place.toilet_score}点`}<br />
              信頼度: {place.trust_score == null ? "未計算" : place.trust_score.toFixed(0)}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
