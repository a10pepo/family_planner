/** Prepare a small local preview; the API independently validates the image. */
export async function preparePhoto(file: File): Promise<string> {
  if (!["image/jpeg", "image/png", "image/webp"].includes(file.type))
    throw new Error("Elige una foto JPG, PNG o WebP.");
  if (file.size > 5 * 1024 * 1024)
    throw new Error("La foto no puede superar 5 MB.");
  const bitmap = await createImageBitmap(file).catch(() => {
    throw new Error("No se ha podido abrir esta foto.");
  });
  try {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 256;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("No se ha podido preparar la foto.");
    context.fillStyle = "white";
    context.fillRect(0, 0, 256, 256);
    const side = Math.min(bitmap.width, bitmap.height);
    context.drawImage(
      bitmap,
      (bitmap.width - side) / 2,
      (bitmap.height - side) / 2,
      side,
      side,
      0,
      0,
      256,
      256,
    );
    return canvas.toDataURL("image/jpeg", 0.9);
  } finally {
    bitmap.close();
  }
}
