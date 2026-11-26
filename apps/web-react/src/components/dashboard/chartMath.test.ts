import { describe, expect, it } from "vitest";
import {
  areaPath,
  axisAmountLabel,
  labelIndices,
  linePath,
  nearestIndex,
  niceStep,
  scaleLinear,
  ticksWithin,
  zeroBasedTicks,
} from "./chartMath";

describe("scaleLinear", () => {
  it("maps the domain onto the range, also inverted (SVG y grows downwards)", () => {
    const x = scaleLinear([0, 10], [100, 200]);
    expect(x(0)).toBe(100);
    expect(x(5)).toBe(150);
    expect(x(10)).toBe(200);

    const y = scaleLinear([0, 100], [216, 24]);
    expect(y(0)).toBe(216);
    expect(y(100)).toBe(24);
    expect(y(50)).toBe(120);
  });

  it("puts everything in the middle for a zero-width domain (a single point)", () => {
    const x = scaleLinear([3, 3], [0, 100]);
    expect(x(3)).toBe(50);
    expect(x(99)).toBe(50);
  });
});

describe("niceStep / ticks", () => {
  it("picks 1, 2, 2.5 or 5 times a power of ten", () => {
    expect(niceStep(30000, 4)).toBe(10000);
    expect(niceStep(100, 4)).toBe(25);
    expect(niceStep(7, 4)).toBe(2);
    expect(niceStep(0.9, 3)).toBe(0.5);
  });

  it("never returns 2.5 or less than 1 for integer axes (months)", () => {
    expect(niceStep(100, 4, true)).toBe(50);
    expect(niceStep(13, 4, true)).toBe(5);
    expect(niceStep(3, 10, true)).toBe(1);
  });

  it("zeroBasedTicks reaches at least the maximum", () => {
    expect(zeroBasedTicks(30000)).toEqual([0, 10000, 20000, 30000]);
    expect(zeroBasedTicks(31000)).toEqual([0, 10000, 20000, 30000, 40000]);
    expect(zeroBasedTicks(90000)).toEqual([0, 25000, 50000, 75000, 100000]);
    expect(zeroBasedTicks(0)).toEqual([0]);
  });

  it("ticksWithin stays inside the data and starts at 0", () => {
    expect(ticksWithin(13, 4, true)).toEqual([0, 5, 10]);
    expect(ticksWithin(600, 5, true)).toEqual([0, 200, 400, 600]);
    expect(ticksWithin(600, 8, true)).toEqual([0, 100, 200, 300, 400, 500, 600]);
    expect(ticksWithin(1, 4, true)).toEqual([0, 1]);
    expect(ticksWithin(0, 4, true)).toEqual([0]);
  });
});

describe("nearestIndex", () => {
  it("finds the closest position (the crosshair snaps to it)", () => {
    const xs = [10, 50, 90, 130];
    expect(nearestIndex(xs, -20)).toBe(0);
    expect(nearestIndex(xs, 31)).toBe(1);
    expect(nearestIndex(xs, 69)).toBe(1);
    expect(nearestIndex(xs, 71)).toBe(2);
    expect(nearestIndex(xs, 500)).toBe(3);
    expect(nearestIndex([], 5)).toBe(-1);
  });
});

describe("labelIndices", () => {
  it("labels every point when they fit", () => {
    expect(labelIndices(4, 6)).toEqual([0, 1, 2, 3]);
    expect(labelIndices(1, 6)).toEqual([0]);
    expect(labelIndices(0, 6)).toEqual([]);
  });

  it("thins evenly and always keeps the first and the last", () => {
    expect(labelIndices(12, 4)).toEqual([0, 4, 7, 11]);
    expect(labelIndices(12, 2)).toEqual([0, 11]);
    // a very narrow plot still gets the two ends
    expect(labelIndices(12, 0)).toEqual([0, 11]);
  });
});

describe("paths", () => {
  it("draws a line through the points and closes the area down to the baseline", () => {
    const points = [
      { x: 0, y: 10 },
      { x: 50.04, y: 20.06 },
    ];
    expect(linePath(points)).toBe("M0 10 L50 20.1");
    expect(areaPath(points, 100)).toBe("M0 10 L50 20.1 L50 100 L0 100 Z");
    expect(linePath([])).toBe("");
    expect(areaPath([], 100)).toBe("");
  });
});

describe("axisAmountLabel", () => {
  it("writes amounts in full under 10.000 and compact (tr-TR) once the axis reaches it", () => {
    expect(axisAmountLabel(2500, 5000)).toBe("2.500");
    // Intl keeps the unit with a no-break space
    expect(axisAmountLabel(30000, 40000)).toBe("30\u00a0B");
    expect(axisAmountLabel(1500000, 2000000)).toBe("1,5\u00a0Mn");
    expect(axisAmountLabel(0, 40000)).toBe("0");
  });
});
