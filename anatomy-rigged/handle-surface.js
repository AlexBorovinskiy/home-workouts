// Coordinates are in the handle frame. Its exposed cylindrical shaft runs along X.
function clipAxialPlane(polygon, limit, sign) {
  const result = [];
  for (let i = 0; i < polygon.length; i++) {
    const a = polygon[i], b = polygon[(i + 1) % polygon.length];
    const insideA = sign * (a.x - limit) <= 0;
    const insideB = sign * (b.x - limit) <= 0;
    if (insideA) result.push(a);
    if (insideA !== insideB) {
      const t = (limit - a.x) / (b.x - a.x);
      result.push({x: limit, y: a.y + t * (b.y - a.y), z: a.z + t * (b.z - a.z)});
    }
  }
  return result;
}

function minimumRadiusSquared(polygon) {
  let nearest = Infinity, positive = false, negative = false, area = 0;
  for (let i = 0; i < polygon.length; i++) {
    const a = polygon[i], b = polygon[(i + 1) % polygon.length];
    const cross = a.y * b.z - a.z * b.y;
    area += cross;
    positive ||= cross > 0;
    negative ||= cross < 0;
    const dy = b.y - a.y, dz = b.z - a.z;
    const squaredLength = dy * dy + dz * dz;
    const t = squaredLength ? Math.max(0, Math.min(1, -(a.y * dy + a.z * dz) / squaredLength)) : 0;
    nearest = Math.min(nearest, (a.y + t * dy) ** 2 + (a.z + t * dz) ** 2);
  }
  return area !== 0 && !(positive && negative) ? 0 : nearest;
}

export function measureHandleSurface(vertices, index, halfShaft, radius) {
  const count = index ? index.count : vertices.length;
  let minRadialGapM = Infinity, trianglesInShaft = 0, penetratingTriangles = 0;
  for (let i = 0; i < count; i += 3) {
    const points = [];
    for (let j = i; j < i + 3; j++) points.push(vertices[index ? index.getX(j) : j]);
    const clipped = clipAxialPlane(clipAxialPlane(points, halfShaft, 1), -halfShaft, -1);
    if (!clipped.length) continue;
    trianglesInShaft++;
    const gap = Math.sqrt(minimumRadiusSquared(clipped)) - radius;
    minRadialGapM = Math.min(minRadialGapM, gap);
    if (gap < -1e-9) penetratingTriangles++;
  }
  return {trianglesInShaft, penetratingTriangles, minRadialGapM: Number.isFinite(minRadialGapM) ? minRadialGapM : null};
}
