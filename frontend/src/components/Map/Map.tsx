import { MapContainer, TileLayer } from 'react-leaflet';
import { SpotMarkers } from './SpotMarkers';
import 'leaflet/dist/leaflet.css';

export function Map() {
  return (
    <MapContainer
      center={[20, 0]}
      zoom={2}
      className="h-screen w-screen"
      minZoom={2}
      maxZoom={18}
      worldCopyJump={true}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <SpotMarkers />
    </MapContainer>
  );
}
