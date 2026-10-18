// Hands a photo picked on the landing page over to /donate, so giving
// something starts with a single tap.
let photo = null;

/** @param {File | null} file */
export function setPendingPhoto(file) {
  photo = file;
}

/** Returns the waiting photo once, then forgets it. */
export function takePendingPhoto() {
  const file = photo;
  photo = null;
  return file;
}
