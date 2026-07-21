export type PayrollProjectionDifference = {
  direction: "higher" | "lower";
  color: "green" | "orange" | "red";
  percentage: number | null;
};

const DIFFERENCE_THRESHOLD = 0.05;
const RED_DIFFERENCE_THRESHOLD = 0.25;

function finiteNumber(value: string | null): number | null {
  if (value == null || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

export function comparePayrollProjection(
  projectedValue: string | null,
  actualValue: string | null,
): PayrollProjectionDifference | null {
  const projected = finiteNumber(projectedValue);
  const actual = finiteNumber(actualValue);
  if (projected == null || actual == null) return null;

  const difference = projected - actual;
  if (difference === 0) return null;
  if (actual === 0) {
    return {
      direction: difference > 0 ? "higher" : "lower",
      color: difference > 0 ? "green" : "red",
      percentage: null,
    };
  }

  const ratio = Math.abs(difference) / Math.abs(actual);
  if (ratio <= DIFFERENCE_THRESHOLD) return null;
  const direction = difference > 0 ? "higher" : "lower";
  if (direction === "higher" && ratio <= RED_DIFFERENCE_THRESHOLD) return null;
  const color = direction === "higher"
    ? "green"
    : ratio > RED_DIFFERENCE_THRESHOLD
      ? "red"
      : "orange";
  return {
    direction,
    color,
    percentage: ratio * 100,
  };
}

export function compareDailyPayrollProjection(
  projectedValue: string | null,
  actualValue: string | null,
): PayrollProjectionDifference | null {
  const projected = finiteNumber(projectedValue);
  const actual = finiteNumber(actualValue);
  if (projected == null || actual == null) return null;

  const difference = projected - actual;
  if (difference === 0) return null;
  if (actual === 0) {
    return {
      direction: difference > 0 ? "higher" : "lower",
      color: difference > 0 ? "green" : "red",
      percentage: null,
    };
  }

  const ratio = Math.abs(difference) / Math.abs(actual);
  const direction = difference > 0 ? "higher" : "lower";
  return {
    direction,
    color: direction === "higher"
      ? "green"
      : ratio > RED_DIFFERENCE_THRESHOLD
        ? "red"
        : "orange",
    percentage: ratio * 100,
  };
}
