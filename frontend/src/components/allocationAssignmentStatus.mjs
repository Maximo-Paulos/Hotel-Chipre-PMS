/**
 * @param {string} status
 * @param {number | null} sourceRoomId
 * @param {number | null} targetRoomId
 * @returns {string}
 */
export function allocationAssignmentStatusKey(status, sourceRoomId, targetRoomId) {
  const normalizedStatus = status.toLowerCase();
  if (normalizedStatus === "applied" && sourceRoomId !== null && sourceRoomId === targetRoomId) {
    return "retained";
  }
  return normalizedStatus;
}
