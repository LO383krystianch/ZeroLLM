/* zipExport.js — lekki, bezdependencyjny generator archiwów ZIP (w 100% w
 * przeglądarce, działa też offline, bez zewnętrznych CDN-ów).
 *
 * Implementacja formatu ZIP z metodą STORE (bez kompresji) + CRC32.
 * Obsługuje nazwy UTF-8 (polskie znaki) oraz wpisy katalogów.
 *
 * API:
 *   ZipExport.downloadZip(filename, entries)
 *     entries: [{ name: string, data: Uint8Array }]
 */
(function () {
  "use strict";

  /* ---- CRC32 (standard, wielomian 0xEDB88320, reflected) ---- */
  var CRC_TABLE = (function () {
    var table = new Uint32Array(256);
    for (var n = 0; n < 256; n++) {
      var c = n;
      for (var k = 0; k < 8; k++) {
        c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
      }
      table[n] = c >>> 0;
    }
    return table;
  })();

  function crc32(bytes) {
    var c = 0xFFFFFFFF;
    for (var i = 0; i < bytes.length; i++) {
      c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
    }
    return (c ^ 0xFFFFFFFF) >>> 0;
  }

  // Stała data w formacie DOS: 2024-01-01 00:00:00.
  var DOS_TIME = 0;
  var DOS_DATE = 0x5821;

  var encoder = typeof TextEncoder !== "undefined" ? new TextEncoder() : null;

  function utf8(str) {
    return encoder.encode(str);
  }

  function concat(arrays) {
    var total = 0;
    for (var i = 0; i < arrays.length; i++) {
      total += arrays[i].length;
    }
    var out = new Uint8Array(total);
    var pos = 0;
    for (var j = 0; j < arrays.length; j++) {
      out.set(arrays[j], pos);
      pos += arrays[j].length;
    }
    return out;
  }

  /* ---- Budowanie archiwum ZIP (metoda STORE) ---- */
  function buildZip(entries) {
    var localParts = [];
    var centralParts = [];
    var offset = 0;

    for (var e = 0; e < entries.length; e++) {
      var entry = entries[e];
      var isDir = entry.name.charAt(entry.name.length - 1) === "/";
      var nameBytes = utf8(entry.name);
      var data = entry.data || new Uint8Array(0);
      var crc = crc32(data);
      var size = data.length;
      var externalAttrs = isDir ? 0x10 : 0;

      // Local file header (30 B) + nazwa + dane.
      var local = new DataView(new ArrayBuffer(30));
      local.setUint32(0, 0x04034b50, true);
      local.setUint16(4, 20, true);       // version needed
      local.setUint16(6, 0x0800, true);   // flag bit 11 = UTF-8 names
      local.setUint16(8, 0, true);        // method = STORE
      local.setUint16(10, DOS_TIME, true);
      local.setUint16(12, DOS_DATE, true);
      local.setUint32(14, crc, true);
      local.setUint32(18, size, true);    // compressed size
      local.setUint32(22, size, true);    // uncompressed size
      local.setUint16(26, nameBytes.length, true);
      local.setUint16(28, 0, true);       // extra field length

      localParts.push(new Uint8Array(local.buffer), nameBytes, data);

      // Central directory header (46 B) + nazwa.
      var central = new DataView(new ArrayBuffer(46));
      central.setUint32(0, 0x02014b50, true);
      central.setUint16(4, 20, true);     // version made by
      central.setUint16(6, 20, true);     // version needed
      central.setUint16(8, 0x0800, true); // UTF-8
      central.setUint16(10, 0, true);     // method = STORE
      central.setUint16(12, DOS_TIME, true);
      central.setUint16(14, DOS_DATE, true);
      central.setUint32(16, crc, true);
      central.setUint32(20, size, true);
      central.setUint32(24, size, true);
      central.setUint16(28, nameBytes.length, true);
      central.setUint16(30, 0, true);     // extra field length
      central.setUint16(32, 0, true);     // comment length
      central.setUint16(34, 0, true);     // disk number start
      central.setUint16(36, 0, true);     // internal attrs
      central.setUint32(38, externalAttrs, true);
      central.setUint32(42, offset, true);// relative offset of local header

      centralParts.push(new Uint8Array(central.buffer), nameBytes);

      offset += 30 + nameBytes.length + size;
    }

    var localBytes = concat(localParts);
    var centralBytes = concat(centralParts);

    // End of central directory (22 B).
    var eocd = new DataView(new ArrayBuffer(22));
    eocd.setUint32(0, 0x06054b50, true);
    eocd.setUint16(4, 0, true);           // number of this disk
    eocd.setUint16(6, 0, true);           // disk with central directory
    eocd.setUint16(8, entries.length, true);
    eocd.setUint16(10, entries.length, true);
    eocd.setUint32(12, centralBytes.length, true);
    eocd.setUint32(16, localBytes.length, true);
    eocd.setUint16(20, 0, true);          // comment length

    return concat([localBytes, centralBytes, new Uint8Array(eocd.buffer)]);
  }

  /* ---- Wyznacza wpisy katalogów dla ścieżek z podfolderami ---- */
  function buildDirectoryEntries(entries) {
    var dirs = {};
    for (var i = 0; i < entries.length; i++) {
      var parts = entries[i].name.split("/");
      if (parts.length <= 1) {
        continue;
      }
      var acc = "";
      for (var j = 0; j < parts.length - 1; j++) {
        acc += parts[j] + "/";
        dirs[acc] = true;
      }
    }
    var result = [];
    for (var d in dirs) {
      if (Object.prototype.hasOwnProperty.call(dirs, d)) {
        result.push({ name: d, data: new Uint8Array(0) });
      }
    }
    return result;
  }

  function downloadZip(filename, entries) {
    var all = buildDirectoryEntries(entries).concat(entries);
    var bytes = buildZip(all);
    var blob = new Blob([bytes], { type: "application/zip" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 0);
  }

  window.ZipExport = {
    crc32: crc32,
    buildZip: buildZip,
    downloadZip: downloadZip,
  };
})();
