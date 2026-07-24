// Deterministic viewport selection for the public facility map.

export type MapCoordinate = {
  latitude: number;
  longitude: number;
};

export type MapViewport =
  | {
      kind: "center";
      center: [number, number];
      zoom: number;
      key: string;
    }
  | {
      kind: "bounds";
      bounds: [[number, number], [number, number]];
      key: string;
    };

export const DEFAULT_MAP_CENTER: [number, number] = [36.2048, 138.2529];

function isValidCoordinate(coordinate: MapCoordinate): boolean {
  return (
    Number.isFinite(coordinate.latitude) &&
    Number.isFinite(coordinate.longitude) &&
    coordinate.latitude >= -90 &&
    coordinate.latitude <= 90 &&
    coordinate.longitude >= -180 &&
    coordinate.longitude <= 180
  );
}

function centered(coordinate: MapCoordinate, zoom: number): MapViewport {
  const center: [number, number] = [coordinate.latitude, coordinate.longitude];
  return { kind: "center", center, zoom, key: `center:${center[0]}:${center[1]}:${zoom}` };
}

export function resolveMapViewport(
  places: readonly MapCoordinate[],
  userLocation: MapCoordinate | null,
): MapViewport {
  if (userLocation && isValidCoordinate(userLocation)) {
    return centered(userLocation, 13);
  }

  const validPlaces = places.filter(isValidCoordinate);
  if (validPlaces.length === 0) {
    return centered({ latitude: DEFAULT_MAP_CENTER[0], longitude: DEFAULT_MAP_CENTER[1] }, 5);
  }
  if (validPlaces.length === 1) {
    return centered(validPlaces[0], 13);
  }

  let south = validPlaces[0].latitude;
  let north = validPlaces[0].latitude;
  let west = validPlaces[0].longitude;
  let east = validPlaces[0].longitude;
  for (const place of validPlaces.slice(1)) {
    south = Math.min(south, place.latitude);
    north = Math.max(north, place.latitude);
    west = Math.min(west, place.longitude);
    east = Math.max(east, place.longitude);
  }

  if (south === north && west === east) {
    return centered(validPlaces[0], 13);
  }

  const bounds: [[number, number], [number, number]] = [
    [south, west],
    [north, east],
  ];
  return { kind: "bounds", bounds, key: `bounds:${south}:${west}:${north}:${east}` };
}
