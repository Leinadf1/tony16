export default async function handler(req, res) {
  // Il link RAW della tua lista su GitHub
  const url = "https://raw.githubusercontent.com/Leinadf1/tony16/main/lista.m3u";

  try {
    const response = await fetch(url + "?v=" + Date.now());
    const data = await response.text();

    // Se GitHub risponde con un errore HTML, lo blocchiamo qui
    if (data.includes("<!DOCTYPE html>")) {
      return res.status(500).json({ error: "GitHub non restituisce il file corretto" });
    }

    // Rispediamo il testo della lista al tuo index.html
    res.setHeader('Content-Type', 'text/plain');
    res.status(200).send(data);
  } catch (error) {
    res.status(500).json({ error: "Errore nel recupero della lista" });
  }
}
