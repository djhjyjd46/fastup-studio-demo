/**
 * FastUp Google Docs Bridge + Markdown Renderer + File Organizer + Binary Uploader
 * 
 * Разворачивается в https://script.google.com под аккаунтом fastup.by@gmail.com
 * Корневая папка компании «Акты/Договоры FastUp»: 1YIvypoZFWwxmpQby2LOOXhI4LoeHFUDl
 */

var DEFAULT_FOLDER_ID = "1YIvypoZFWwxmpQby2LOOXhI4LoeHFUDl";

/**
 * Секрет шлюза хранится НЕ в коде (копии кода лежат в репозиториях), а в свойствах скрипта:
 * Настройки проекта → Свойства скрипта → GATEWAY_SECRET. Клиенты (scripts/gdocs.py, сервер
 * tools.fastup.by) шлют его полем "secret" из GDOCS_GAS_SECRET. Свойство не задано — шлюз
 * отказывает всем: открытый шлюз к документам фирмы хуже неработающего.
 */
function checkSecret(data) {
  var expected = PropertiesService.getScriptProperties().getProperty("GATEWAY_SECRET");
  if (!expected) return "GATEWAY_SECRET не задан в свойствах скрипта — шлюз закрыт";
  var got = String(data.secret || "");
  if (got.length !== expected.length) return "forbidden";
  var diff = 0;
  for (var i = 0; i < expected.length; i++) diff |= expected.charCodeAt(i) ^ got.charCodeAt(i);
  return diff === 0 ? null : "forbidden";
}

/** Тело, верхний и нижний колонтитулы документа — везде, где могут стоять поля {{...}}. */
function docSections(doc) {
  var sections = [doc.getBody()];
  if (doc.getHeader()) sections.push(doc.getHeader());
  if (doc.getFooter()) sections.push(doc.getFooter());
  return sections;
}

/** replaceText принимает регулярное выражение — экранируем, чтобы {{sum}} искался буквально. */
function escapeRegex(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var denied = checkSecret(data);
    if (denied) return jsonResponse({ ok: false, error: denied });
    var action = data.action;
    var folderId = data.folderId || DEFAULT_FOLDER_ID;

    // 1. Поиск и список файлов (рекурсивный или с фильтрацией)
    if (action === "gdrive_list") {
      var root = DriveApp.getFolderById(folderId);
      var files = [];
      var query = (data.query || "").toLowerCase();

      var startFolder = root;
      var startPath = "";
      if (data.folderName) {
        startFolder = resolveTargetFolder("", data.folderName, root);
        startPath = data.folderName;
      }

      collectFilesRecursive(startFolder, query, files, startPath);
      return jsonResponse({ ok: true, data: files });
    }

    // 2. Список всех подпапок
    if (action === "gdrive_list_folders") {
      var root = DriveApp.getFolderById(folderId);
      var folders = [];
      var itF = root.getFolders();
      while (itF.hasNext()) {
        var f = itF.next();
        folders.push({
          id: f.getId(),
          name: f.getName(),
          url: f.getUrl()
        });
      }
      return jsonResponse({ ok: true, data: folders });
    }

    // 3. Чтение текста документа Google Docs
    if (action === "gdrive_read_doc") {
      var doc = DocumentApp.openById(data.fileId);
      var text = doc.getBody().getText();
      return jsonResponse({ ok: true, data: text });
    }

    // 4. Создание документа Google Docs из Markdown
    if (action === "gdocs_create") {
      var root = DriveApp.getFolderById(folderId);
      var targetFolder = resolveTargetFolder(data.title, data.folderName, root);

      var doc = DocumentApp.create(data.title);
      var file = DriveApp.getFileById(doc.getId());
      file.moveTo(targetFolder);

      var content = data.content || "";
      if (content) {
        renderMarkdownToDoc(doc, content);
      }
      doc.saveAndClose();
      return jsonResponse({
        ok: true,
        data: {
          id: file.getId(),
          folder: targetFolder.getName(),
          folderId: targetFolder.getId(),
          url: file.getUrl()
        }
      });
    }

    // 5. Копирование шаблона
    if (action === "gdocs_copy_template") {
      var root = DriveApp.getFolderById(folderId);
      var targetFolder = resolveTargetFolder(data.title, data.folderName, root);

      var template = DriveApp.getFileById(data.templateFileId);
      var copy = template.makeCopy(data.title, targetFolder);
      return jsonResponse({
        ok: true,
        data: {
          id: copy.getId(),
          folder: targetFolder.getName(),
          folderId: targetFolder.getId(),
          url: copy.getUrl()
        }
      });
    }

    // 6. Замена плейсхолдеров — в теле и в колонтитулах; find ищется буквально
    //    (literal: false — старое поведение, find как регулярное выражение).
    if (action === "gdocs_replace") {
      var doc = DocumentApp.openById(data.fileId);
      var pairs = data.pairs || [];
      var sections = docSections(doc);
      for (var i = 0; i < pairs.length; i++) {
        var pattern = data.literal === false ? pairs[i].find : escapeRegex(pairs[i].find);
        for (var s = 0; s < sections.length; s++) {
          sections[s].replaceText(pattern, String(pairs[i].replace));
        }
      }
      doc.saveAndClose();
      return jsonResponse({ ok: true, data: { fileId: data.fileId } });
    }

    // 6а. Какие поля {{...}} есть в документе (тело + колонтитулы) — список полей шаблона
    //     и проверка, что после заполнения ничего не осталось.
    if (action === "gdocs_placeholders") {
      var docP = DocumentApp.openById(data.fileId);
      var found = {};
      var secs = docSections(docP);
      for (var k = 0; k < secs.length; k++) {
        var m = secs[k].getText().match(/\{\{[^{}]+\}\}/g) || [];
        for (var n = 0; n < m.length; n++) found[m[n]] = true;
      }
      return jsonResponse({ ok: true, data: { fileId: data.fileId, placeholders: Object.keys(found).sort() } });
    }

    // 6б. Записать текст колонтитулов (создаёт их при отсутствии). Номер страницы полем
    //     Apps Script вставить не умеет — «Страница X из Y» ставится в шаблоне руками один раз.
    if (action === "gdocs_set_header_footer") {
      var docH = DocumentApp.openById(data.fileId);
      if (typeof data.header === "string") {
        var header = docH.getHeader() || docH.addHeader();
        header.clear();
        header.appendParagraph(data.header).setFontSize(8);
      }
      if (typeof data.footer === "string") {
        var footer = docH.getFooter() || docH.addFooter();
        footer.clear();
        footer.appendParagraph(data.footer).setFontSize(8);
      }
      docH.saveAndClose();
      return jsonResponse({ ok: true, data: { fileId: data.fileId } });
    }

    // 7. Экспорт Google Doc в PDF файл на Диске
    if (action === "gdocs_export_pdf") {
      var docFile = DriveApp.getFileById(data.fileId);
      var pdfBlob = docFile.getAs("application/pdf");
      var pdfName = data.fileName || (docFile.getName() + ".pdf");
      var root = DriveApp.getFolderById(folderId);
      var targetFolder = root;
      if (data.folderId) {
        targetFolder = DriveApp.getFolderById(data.folderId);
      } else if (data.folderName) {
        targetFolder = resolveTargetFolder(pdfName, data.folderName, root);
      }
      var pdfFile = targetFolder.createFile(pdfBlob.setName(pdfName));
      return jsonResponse({
        ok: true,
        data: {
          id: pdfFile.getId(),
          name: pdfFile.getName(),
          folder: targetFolder.getName(),
          url: pdfFile.getUrl()
        }
      });
    }

    // 8. Загрузка бинарного файла (PDF, скан, чек, изображение) через base64
    if (action === "gdrive_upload_file") {
      var root = DriveApp.getFolderById(folderId);
      var targetFolder = root;
      if (data.folderId) {
        targetFolder = DriveApp.getFolderById(data.folderId);
      } else if (data.folderName) {
        targetFolder = resolveTargetFolder(data.fileName, data.folderName, root);
      }

      var bytes = Utilities.base64Decode(data.base64Data);
      var blob = Utilities.newBlob(bytes, data.mimeType || "application/pdf", data.fileName);

      // Проверка на дубликат по имени в целевой папке
      var existing = targetFolder.getFilesByName(data.fileName);
      if (existing.hasNext() && data.overwrite === true) {
        var oldFile = existing.next();
        oldFile.setTrashed(true);
      }

      var file = targetFolder.createFile(blob);
      return jsonResponse({
        ok: true,
        data: {
          id: file.getId(),
          name: file.getName(),
          folder: targetFolder.getName(),
          folderId: targetFolder.getId(),
          url: file.getUrl()
        }
      });
    }

    // 9. Пакетная загрузка массива файлов (batch upload)
    if (action === "gdrive_upload_batch") {
      var root = DriveApp.getFolderById(folderId);
      var filesList = data.files || [];
      var results = [];
      for (var b = 0; b < filesList.length; b++) {
        var item = filesList[b];
        try {
          var tFolder = root;
          if (item.folderId) {
            tFolder = DriveApp.getFolderById(item.folderId);
          } else if (item.folderName) {
            tFolder = resolveTargetFolder(item.fileName, item.folderName, root);
          }

          var bBytes = Utilities.base64Decode(item.base64Data);
          var bBlob = Utilities.newBlob(bBytes, item.mimeType || "application/pdf", item.fileName);
          var bFile = tFolder.createFile(bBlob);
          results.push({
            name: item.fileName,
            id: bFile.getId(),
            url: bFile.getUrl(),
            folder: tFolder.getName(),
            status: "ok"
          });
        } catch (errB) {
          results.push({
            name: item.fileName,
            error: errB.toString(),
            status: "error"
          });
        }
      }
      return jsonResponse({ ok: true, data: results });
    }

    // 10. Скачивание файла в base64
    if (action === "gdrive_download_file") {
      var fDown = DriveApp.getFileById(data.fileId);
      var blobDown = fDown.getBlob();
      var b64Down = Utilities.base64Encode(blobDown.getBytes());
      return jsonResponse({
        ok: true,
        data: {
          id: fDown.getId(),
          name: fDown.getName(),
          mimeType: blobDown.getContentType(),
          base64Data: b64Down
        }
      });
    }

    // 11. Переименование файла или папки
    if (action === "gdrive_rename") {
      var newName = data.name;
      if (!newName) return jsonResponse({ ok: false, error: "Не указано новое имя" });

      try {
        var targetF = DriveApp.getFileById(data.id);
        targetF.setName(newName);
        return jsonResponse({ ok: true, data: { id: data.id, name: newName } });
      } catch (e1) {
        var targetFold = DriveApp.getFolderById(data.id);
        targetFold.setName(newName);
        return jsonResponse({ ok: true, data: { id: data.id, name: newName } });
      }
    }

    // 12. Перемещение файла в папку
    if (action === "gdrive_move_file") {
      var fToMove = DriveApp.getFileById(data.fileId);
      var destFolder = DriveApp.getFolderById(data.targetFolderId);
      fToMove.moveTo(destFolder);
      return jsonResponse({
        ok: true,
        data: { fileId: data.fileId, targetFolderId: data.targetFolderId, name: fToMove.getName() }
      });
    }

    // 13. Перемещение в корзину (один файл или массив)
    if (action === "gdrive_trash") {
      var fileIds = Array.isArray(data.fileIds) ? data.fileIds : (data.fileId ? [data.fileId] : []);
      if (fileIds.length === 0) {
        return jsonResponse({ ok: false, error: "Не указан fileId или fileIds" });
      }
      var trashed = [];
      var errors = [];
      for (var i = 0; i < fileIds.length; i++) {
        try {
          var f = DriveApp.getFileById(fileIds[i]);
          f.setTrashed(true);
          trashed.push({ id: fileIds[i], name: f.getName() });
        } catch (err) {
          try {
            var fold = DriveApp.getFolderById(fileIds[i]);
            fold.setTrashed(true);
            trashed.push({ id: fileIds[i], name: fold.getName() });
          } catch (err2) {
            errors.push({ id: fileIds[i], error: err.toString() });
          }
        }
      }
      return jsonResponse({ ok: true, data: { trashed: trashed, errors: errors } });
    }

    // 14. Создание подпапки
    if (action === "gdrive_create_folder") {
      var parent = DriveApp.getFolderById(folderId);
      var target = getOrCreateFolder(data.name, parent);
      return jsonResponse({
        ok: true,
        data: { id: target.getId(), name: target.getName(), url: target.getUrl() }
      });
    }

    // 15. Генеральная очистка кривых папок и мусора (cleanup)
    if (action === "gdrive_cleanup") {
      var cleanupResult = performGeneralCleanup(folderId);
      return jsonResponse({ ok: true, data: cleanupResult });
    }

    // 16. Авто-раскладка и структурирование всех документов
    if (action === "gdrive_organize") {
      var orgResult = organizeAllDocuments(folderId, data.trashJunk === true);
      return jsonResponse({ ok: true, data: orgResult });
    }

    // 17. Аудит документов
    if (action === "gdrive_audit") {
      var audit = auditAllDocuments(folderId);
      return jsonResponse({ ok: true, data: audit });
    }

    // 18. Документ по спецификации из блоков (единые шаблоны живут на сервере tools.fastup.by:
    //     сервер собирает блоки, здесь только вёрстка). Спецификация — см. renderSpec.
    if (action === "gdocs_render") {
      var rootR = DriveApp.getFolderById(folderId);
      var targetR = data.targetFolderId
        ? DriveApp.getFolderById(data.targetFolderId)
        : resolveTargetFolder(data.title, data.folderName, rootR);
      var docR = DocumentApp.create(data.title);
      var fileR = DriveApp.getFileById(docR.getId());
      fileR.moveTo(targetR);
      renderSpec(docR, data.spec || {});
      docR.saveAndClose();
      return jsonResponse({
        ok: true,
        data: { id: fileR.getId(), url: fileR.getUrl(), folder: targetR.getName(), folderId: targetR.getId() }
      });
    }

    return jsonResponse({ ok: false, error: "Unknown action: " + action });
  } catch (err) {
    return jsonResponse({ ok: false, error: err.toString() });
  }
}

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * Запуск вручную из редактора Google Apps Script:
 * Очищает кривые папки (с ID в названиях), удаляет мусор и раскладывает документы.
 */
function runCleanupAndOrganize() {
  var cleanRes = performGeneralCleanup(DEFAULT_FOLDER_ID);
  Logger.log("ИТОГИ ОЧИСТКИ КРИВЫХ ПАПОК:\n" + JSON.stringify(cleanRes, null, 2));
  var orgRes = organizeAllDocuments(DEFAULT_FOLDER_ID, true);
  Logger.log("ИТОГИ РАСКЛАДКИ ПО ПАПКАМ:\n" + JSON.stringify(orgRes, null, 2));
}

/**
 * Запуск аудита документов из редактора
 */
function runAuditDocs() {
  var res = auditAllDocuments(DEFAULT_FOLDER_ID);
  Logger.log("ИТОГИ АУДИТА ДОКУМЕНТОВ (" + res.length + " шт.):\n" + JSON.stringify(res, null, 2));
}

/**
 * Очистка кривых папок (с ID вместо имени) и перемещение их файлов в правильные места
 */
function performGeneralCleanup(rootFolderId) {
  var root = DriveApp.getFolderById(rootFolderId);
  var fixedFolders = [];
  var trashedFolders = [];
  var movedFiles = [];

  var accountingFolder = getOrCreateFolder("Бухгалтерия — состояние и чек-листы", root);

  var subFoldersIt = root.getFolders();
  while (subFoldersIt.hasNext()) {
    var fold = subFoldersIt.next();
    var fName = fold.getName();
    var fId = fold.getId();

    // 1. Папки, названные raw ID (например, 1_I1FNmymEINGydP4ipCCJZAbdbwFAc1X)
    if (/^[a-zA-Z0-9_-]{25,}$/.test(fName) || fName.indexOf("1_I1FN") === 0) {
      // Переносим файлы из кривой папки в нормальную «Бухгалтерия — состояние и чек-листы»
      var nestedFiles = fold.getFiles();
      while (nestedFiles.hasNext()) {
        var nFile = nestedFiles.next();
        nFile.moveTo(accountingFolder);
        movedFiles.push({ file: nFile.getName(), from: fName, to: "Бухгалтерия — состояние и чек-листы" });
      }
      // Отправляем пустую кривую папку в корзину
      fold.setTrashed(true);
      trashedFolders.push({ id: fId, name: fName, reason: "Имя папки являлось ID" });
    }

    // 2. Плавающая пустая папка «Действующие» в корне
    if (fName === "Действующие") {
      var isEmpty = !fold.getFiles().hasNext() && !fold.getFolders().hasNext();
      if (isEmpty) {
        fold.setTrashed(true);
        trashedFolders.push({ id: fId, name: fName, reason: "Пустая плавающая папка в корне" });
      }
    }
  }

  // 3. Удаление дубликатов ненужных файлов (второй индекс Google Docs)
  var junkFileNames = [
    "ИНДЕКС первичных документов, сканов и чеков"
  ];
  var rootFiles = root.getFiles();
  var trashedFiles = [];
  while (rootFiles.hasNext()) {
    var rf = rootFiles.next();
    if (junkFileNames.indexOf(rf.getName()) !== -1) {
      rf.setTrashed(true);
      trashedFiles.push({ id: rf.getId(), name: rf.getName(), reason: "Дубликат/устаревший черновой индекс" });
    }
  }

  // Также удаляем устаревший индекс из папки Бухгалтерии
  var accFiles = accountingFolder.getFiles();
  while (accFiles.hasNext()) {
    var af = accFiles.next();
    if (af.getName() === "ИНДЕКС первичных документов, сканов и чеков") {
      af.setTrashed(true);
      trashedFiles.push({ id: af.getId(), name: af.getName(), reason: "Дубликат чернового индекса в Бухгалтерии" });
    }
  }

  return {
    movedFiles: movedFiles,
    trashedFolders: trashedFolders,
    trashedFiles: trashedFiles
  };
}

/**
 * Логика фильтрации и раскладки файлов по подпапкам
 */
function organizeAllDocuments(rootFolderId, trashJunk) {
  var root = DriveApp.getFolderById(rootFolderId);

  var folderActs = getOrCreateFolder("Акты", root);
  var folderActsActive = getOrCreateFolder("Действующие", folderActs);
  var folderActsArchive = getOrCreateFolder("Архив", folderActs);
  var folderActsClients = getOrCreateFolder("Клиенты", folderActs);
  var folderActsContractors = getOrCreateFolder("Подрядчики", folderActs);

  var folderContracts = getOrCreateFolder("Договоры", root);
  var folderContractsClients = getOrCreateFolder("Клиенты", folderContracts);
  var folderContractsContractors = getOrCreateFolder("Подрядчики", folderContracts);
  var folderContractsTemplates = getOrCreateFolder("Шаблоны", folderContracts);
  var folderContractsArchive = getOrCreateFolder("Архив", folderContracts);

  var folderChecks = getOrCreateFolder("Чеки НПД", root);
  var folderReports = getOrCreateFolder("Отчёты", root);
  var folderReports2026 = getOrCreateFolder("2026", folderReports);
  var folderBriefs = getOrCreateFolder("Брифы и инструкции", root);
  var folderAccounting = getOrCreateFolder("Бухгалтерия — состояние и чек-листы", root);
  var folderJunk = trashJunk ? null : getOrCreateFolder("Черновики и тесты", root);

  var moved = [];
  var trashed = [];
  var skipped = [];

  var junkIds = [
    "15q6WEcOQl2lvBBnZKPVk4CKI0tORWKC1s4sR9ZiW8fw",
    "1lGsrM5yEkzWcGG08zxS8MGfo4a2bfETJva2GRWHnP_w",
    "1co_O6DVmDgl5b8ldEpAKyPQIQeatSOWKP0ngQ1dwv8E",
    "1p8jGrFz9j42mWzOIQAbGD5vCMyL9QUDyWedibRnqGaQ",
    "1bOgOZLg3iVkHKsqrG6P041SZdh2syPav5EgYL1iBnto",
    "1g6dHB0XRJKM3mdd1XF_ZjQTo8BySpEPbFdu9yPYSOgU",
    "1WZ42jGPgeAW7rDznEyqz1ojsbSK-Gka9NR4hgRHDjuI",
    "18qK0Tvh0074FgSZByYN5z3Fz_rujnUGVaJNJbjptyfQ",
    "1WTR-wZ8SX-WqjwxsNpfph4i2oiMhYlJCY17nY5r2P-8",
    "1iTs0Hsl3ICJYx3Fl9FpvYYzynH-1nJu6K0qeCEOouac",
    "1uwekI7tSsKj2ODFJaGjLPGdMh1IBYMzwO6lKYXunCr0"
  ];

  var filesIt = root.getFiles();
  while (filesIt.hasNext()) {
    var file = filesIt.next();
    var id = file.getId();
    var name = file.getName();
    var lower = name.toLowerCase();

    // Проверяем: мусор или тест?
    var isJunk = junkIds.indexOf(id) !== -1 ||
                 lower.indexOf("тестовый") !== -1 ||
                 lower.indexOf("тест копирования") !== -1 ||
                 lower.indexOf("тест форматирования") !== -1 ||
                 lower === "тест" ||
                 lower === "test" ||
                 lower === "test-ulyana" ||
                 lower === "акт выполненных работ № 1" ||
                 (lower.indexOf("светлана — 11.07–25.07.2026") !== -1);

    if (isJunk) {
      if (trashJunk) {
        file.setTrashed(true);
        trashed.push({ id: id, name: name, action: "trashed" });
      } else {
        file.moveTo(folderJunk);
        moved.push({ id: id, name: name, to: "Черновики и тесты" });
      }
      continue;
    }

    // Чеки НПД
    if (lower.indexOf("чек") !== -1 || lower.indexOf("нпд") !== -1) {
      file.moveTo(folderChecks);
      moved.push({ id: id, name: name, to: "Чеки НПД" });
      continue;
    }

    // Шаблоны и примеры
    var isTemplate = lower.indexOf("пример") !== -1 ||
                     lower.indexOf("шаблон") !== -1 ||
                     lower === "договоры";
    if (isTemplate) {
      file.moveTo(folderContractsTemplates);
      moved.push({ id: id, name: name, to: "Договоры/Шаблоны" });
      continue;
    }

    // Договоры клиентов
    if ((lower.indexOf("договор") !== -1) && (lower.indexOf("ооо") !== -1 || lower.indexOf("архиватор") !== -1 || lower.indexOf("сплавар") !== -1 || lower.indexOf("полисак") !== -1 || lower.indexOf("купец") !== -1 || lower.indexOf("роботикс") !== -1)) {
      file.moveTo(folderContractsClients);
      moved.push({ id: id, name: name, to: "Договоры/Клиенты" });
      continue;
    }

    // Договоры подрядчиков
    if (lower.indexOf("договор") !== -1) {
      file.moveTo(folderContractsContractors);
      moved.push({ id: id, name: name, to: "Договоры/Подрядчики" });
      continue;
    }

    // Акты
    if (lower.indexOf("акт") !== -1) {
      if (lower.indexOf("ооо") !== -1 || lower.indexOf("сплавар") !== -1 || lower.indexOf("архиватор") !== -1) {
        file.moveTo(folderActsClients);
        moved.push({ id: id, name: name, to: "Акты/Клиенты" });
      } else {
        file.moveTo(folderActsActive);
        moved.push({ id: id, name: name, to: "Акты/Действующие" });
      }
      continue;
    }

    // Отчёты
    if (lower.indexOf("отчёт") !== -1 || lower.indexOf("отчет") !== -1 || lower.indexOf("сводный") !== -1) {
      file.moveTo(folderReports2026);
      moved.push({ id: id, name: name, to: "Отчёты/2026" });
      continue;
    }

    // Брифы и инструкции
    if (lower.indexOf("бриф") !== -1 || lower.indexOf("инструкци") !== -1) {
      file.moveTo(folderBriefs);
      moved.push({ id: id, name: name, to: "Брифы и инструкции" });
      continue;
    }

    // Документы бухгалтерии
    if (lower.indexOf("бухгалтерия") !== -1 || lower.indexOf("распечатать") !== -1 || lower.indexOf("подрядчикам") !== -1) {
      file.moveTo(folderAccounting);
      moved.push({ id: id, name: name, to: "Бухгалтерия — состояние и чек-листы" });
      continue;
    }

    skipped.push({ id: id, name: name });
  }

  return {
    moved: moved,
    trashed: trashed,
    skipped: skipped
  };
}

/**
 * Рекурсивный сбор файлов по всем подпапкам
 */
function collectFilesRecursive(folder, query, files, currentPath) {
  var itFiles = folder.getFiles();
  while (itFiles.hasNext()) {
    var f = itFiles.next();
    var name = f.getName();
    if (!query || name.toLowerCase().indexOf(query) !== -1) {
      files.push({
        id: f.getId(),
        name: name,
        folder: currentPath || folder.getName(),
        folderId: folder.getId(),
        mimeType: f.getMimeType(),
        modifiedTime: f.getLastUpdated().toISOString(),
        webViewLink: f.getUrl()
      });
    }
  }

  var itFolders = folder.getFolders();
  while (itFolders.hasNext()) {
    var sub = itFolders.next();
    var subPath = currentPath ? (currentPath + "/" + sub.getName()) : sub.getName();
    collectFilesRecursive(sub, query, files, subPath);
  }
}

/**
 * Умная маршрутизация: определяет целевую подпапку по названию или пути
 */
function resolveTargetFolder(title, folderName, rootFolder) {
  if (folderName) {
    // Если передан raw ID существующей папки
    if (/^[a-zA-Z0-9_-]{25,}$/.test(folderName)) {
      try {
        return DriveApp.getFolderById(folderName);
      } catch (eID) {}
    }

    var parts = folderName.split("/");
    var curr = rootFolder;
    for (var p = 0; p < parts.length; p++) {
      var part = parts[p].trim();
      if (part) curr = getOrCreateFolder(part, curr);
    }
    return curr;
  }

  var lower = (title || "").toLowerCase();

  // Чеки НПД
  if (lower.indexOf("чек") !== -1) {
    return getOrCreateFolder("Чеки НПД", rootFolder);
  }

  // Клиентские договоры
  if (lower.indexOf("договор") !== -1 && (lower.indexOf("ооо") !== -1 || lower.indexOf("сплавар") !== -1 || lower.indexOf("архиватор") !== -1 || lower.indexOf("полисак") !== -1)) {
    var d1 = getOrCreateFolder("Договоры", rootFolder);
    return getOrCreateFolder("Клиенты", d1);
  }

  // Договоры с подрядчиками
  if (lower.indexOf("договор") !== -1) {
    var d2 = getOrCreateFolder("Договоры", rootFolder);
    return getOrCreateFolder("Подрядчики", d2);
  }

  // Акты
  if (lower.indexOf("акт") !== -1) {
    var a = getOrCreateFolder("Акты", rootFolder);
    return getOrCreateFolder("Действующие", a);
  }

  // Отчёты
  if (lower.indexOf("отчёт") !== -1 || lower.indexOf("отчет") !== -1) {
    var r = getOrCreateFolder("Отчёты", rootFolder);
    return getOrCreateFolder("2026", r);
  }

  return rootFolder;
}

/**
 * Получить или создать папку по имени внутри родительской
 */
function getOrCreateFolder(name, parentFolder) {
  var it = parentFolder.getFoldersByName(name);
  if (it.hasNext()) {
    return it.next();
  }
  return parentFolder.createFolder(name);
}

/**
 * Анализ всех документов в папке: шапка, даты, определение статуса
 */
function auditAllDocuments(rootFolderId) {
  var root = DriveApp.getFolderById(rootFolderId);
  var files = [];
  collectFilesRecursive(root, "", files, "");

  var audit = [];
  for (var i = 0; i < files.length; i++) {
    var f = files[i];
    audit.push({
      id: f.id,
      name: f.name,
      folder: f.folder,
      mimeType: f.mimeType,
      modifiedTime: f.modifiedTime,
      url: f.webViewLink
    });
  }
  return audit;
}

/**
 * Вёрстка документа по спецификации:
 * {
 *   page: {top, bottom, left, right} — поля в pt (по умолчанию 42.5 / 42.5 / 56.7 / 42.5 = 1,5/1,5/2/1,5 см),
 *   font: "Arial", fontSize: 10,
 *   header: "текст колонтитула", footer: "текст колонтитула",
 *   blocks: [
 *     {type: "title", text, size?},                   — жирный по центру
 *     {type: "center", text, italic?},                — по центру
 *     {type: "para", text, bold?, justify?},          — абзац, **жирный** внутри поддерживается
 *     {type: "pair", left, right},                    — строка «дата слева — город справа»
 *     {type: "list", items: [...], numbered?},        — список
 *     {type: "table", rows: [[...]], header?: true, widths?: [pt,...], boldLastRow?},
 *     {type: "parties", left: [строки], right: [строки]}, — реквизиты и подписи в две колонки без рамок
 *     {type: "spacer"}
 *   ]
 * }
 */
function renderSpec(doc, spec) {
  var body = doc.getBody();
  var page = spec.page || {};
  body.setMarginTop(page.top || 42.5).setMarginBottom(page.bottom || 42.5)
      .setMarginLeft(page.left || 56.7).setMarginRight(page.right || 42.5);
  var base = {};
  base[DocumentApp.Attribute.FONT_FAMILY] = spec.font || "Arial";
  base[DocumentApp.Attribute.FONT_SIZE] = spec.fontSize || 10;
  // Явно: appendParagraph/appendListItem/appendTable наследуют оформление предыдущего
  // абзаца — без сброса жирный заголовок расползался на весь документ.
  base[DocumentApp.Attribute.BOLD] = false;
  base[DocumentApp.Attribute.ITALIC] = false;
  body.clear();
  var firstFree = body.getNumChildren() > 0 ? body.getChild(0).asParagraph() : null;

  function para(text) {
    var p;
    if (firstFree) { p = firstFree; p.setText(text); firstFree = null; }
    else { p = body.appendParagraph(text); }
    p.setAttributes(base);
    p.setSpacingBefore(0).setSpacingAfter(6).setLineSpacing(1.1);
    p.setAlignment(DocumentApp.HorizontalAlignment.LEFT);
    return p;
  }

  function borderlessTable(cells) {
    var t = body.appendTable(cells);
    t.setBorderWidth(0);
    return t;
  }

  var blocks = spec.blocks || [];
  for (var i = 0; i < blocks.length; i++) {
    var b = blocks[i];
    if (b.type === "title") {
      var pt = para(cleanBold(b.text));
      pt.setAlignment(DocumentApp.HorizontalAlignment.CENTER);
      pt.editAsText().setBold(true).setFontSize(b.size || 12);
    } else if (b.type === "center") {
      var pc = para(cleanBold(b.text));
      pc.setAlignment(DocumentApp.HorizontalAlignment.CENTER);
      if (b.italic) pc.editAsText().setItalic(true);
    } else if (b.type === "para") {
      var pp = para(cleanBold(b.text));
      if (b.justify) pp.setAlignment(DocumentApp.HorizontalAlignment.JUSTIFY);
      if (b.bold) pp.editAsText().setBold(true);
      else applyInlineStyles(pp, b.text);
    } else if (b.type === "pair") {
      var tp = borderlessTable([[b.left || "", b.right || ""]]);
      var cl = tp.getCell(0, 0).getChild(0).asParagraph();
      var cr = tp.getCell(0, 1).getChild(0).asParagraph();
      cl.setAttributes(base); cr.setAttributes(base);
      cr.setAlignment(DocumentApp.HorizontalAlignment.RIGHT);
    } else if (b.type === "list") {
      var items = b.items || [];
      for (var li = 0; li < items.length; li++) {
        var item = body.appendListItem(cleanBold(items[li]));
        item.setAttributes(base);
        item.setGlyphType(b.numbered ? DocumentApp.GlyphType.NUMBER : DocumentApp.GlyphType.BULLET);
        item.setSpacingAfter(2);
        applyInlineStyles(item, items[li]);
      }
    } else if (b.type === "table") {
      var rows = (b.rows || []).map(function (r) { return r.map(function (c) { return cleanBold(String(c)); }); });
      if (!rows.length) continue;
      var tt = body.appendTable(rows);
      tt.setBorderColor("#999999").setBorderWidth(0.5);
      for (var r = 0; r < tt.getNumRows(); r++) {
        var row = tt.getRow(r);
        for (var c = 0; c < row.getNumCells(); c++) {
          var cell = row.getCell(c);
          cell.setPaddingTop(2).setPaddingBottom(2);
          if (b.widths && b.widths[c]) cell.setWidth(b.widths[c]);
          var cp = cell.getChild(0).asParagraph();
          cp.setAttributes(base);
          cp.editAsText().setFontSize((spec.fontSize || 10) - 1);
          var isHead = b.header && r === 0;
          var isTotal = b.boldLastRow && r === tt.getNumRows() - 1;
          if (isHead) { cell.setBackgroundColor("#f0f0f0"); cp.editAsText().setBold(true); }
          else if (isTotal) { cp.editAsText().setBold(true); }
          else { applyInlineStyles(cp, String(b.rows[r][c])); }
        }
      }
      para("").setSpacingAfter(2);
    } else if (b.type === "parties") {
      var left = (b.left || []).join("\n");
      var right = (b.right || []).join("\n");
      var tparty = borderlessTable([[cleanBold(left), cleanBold(right)]]);
      var pl = tparty.getCell(0, 0).getChild(0).asParagraph();
      var pr = tparty.getCell(0, 1).getChild(0).asParagraph();
      pl.setAttributes(base); pr.setAttributes(base);
      pl.setLineSpacing(1.15); pr.setLineSpacing(1.15);
      applyInlineStyles(pl, left); applyInlineStyles(pr, right);
    } else if (b.type === "spacer") {
      para("");
    }
  }

  var small = {};
  small[DocumentApp.Attribute.FONT_FAMILY] = spec.font || "Arial";
  small[DocumentApp.Attribute.FONT_SIZE] = 8;
  small[DocumentApp.Attribute.FOREGROUND_COLOR] = "#555555";
  if (spec.header) {
    var h = doc.getHeader() || doc.addHeader();
    h.clear();
    h.appendParagraph(spec.header).setAttributes(small);
  }
  if (spec.footer) {
    var f = doc.getFooter() || doc.addFooter();
    f.clear();
    f.appendParagraph(spec.footer).setAttributes(small);
  }
}

/** Рендерер Markdown в нативные элементы Google Docs */
function renderMarkdownToDoc(doc, markdown) {
  var body = doc.getBody();
  body.clear();
  
  var lines = markdown.split("\n");
  var rawTableRows = [];
  
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i].trim();
    
    if (line.indexOf("|") === 0 || (line.indexOf("|") > 0 && line.lastIndexOf("|") > line.indexOf("|"))) {
      if (/^\|?[\s:-|-]+\|?$/.test(line)) {
        continue;
      }
      var cells = line.split("|").map(function(c) { return c.trim(); });
      if (cells.length > 0 && cells[0] === "") cells.shift();
      if (cells.length > 0 && cells[cells.length - 1] === "") cells.pop();
      if (cells.length > 0) {
        rawTableRows.push(cells);
      }
      continue;
    } else if (rawTableRows.length > 0) {
      flushTable(body, rawTableRows);
      rawTableRows = [];
    }

    if (!line) {
      body.appendParagraph("");
      continue;
    }

    if (line === "---" || line === "***" || line === "___") {
      body.appendHorizontalRule();
      continue;
    }

    var p;
    if (line.indexOf("# ") === 0) {
      p = body.appendParagraph(cleanBold(line.substring(2)));
      p.setHeading(DocumentApp.ParagraphHeading.HEADING1);
    } else if (line.indexOf("## ") === 0) {
      p = body.appendParagraph(cleanBold(line.substring(3)));
      p.setHeading(DocumentApp.ParagraphHeading.HEADING2);
    } else if (line.indexOf("### ") === 0) {
      p = body.appendParagraph(cleanBold(line.substring(4)));
      p.setHeading(DocumentApp.ParagraphHeading.HEADING3);
    } else if (line.indexOf("- ") === 0 || line.indexOf("* ") === 0) {
      var itemText = line.substring(2);
      p = body.appendListItem(cleanBold(itemText));
      applyInlineStyles(p, itemText);
    } else {
      p = body.appendParagraph(cleanBold(line));
      applyInlineStyles(p, line);
    }
  }

  if (rawTableRows.length > 0) {
    flushTable(body, rawTableRows);
  }
}

function flushTable(body, rows) {
  if (rows.length === 0) return;
  var cleanRows = rows.map(function(row) {
    return row.map(function(cell) { return cleanBold(cell); });
  });
  var table = body.appendTable(cleanRows);
  
  table.setBorderColor("#cccccc");
  table.setBorderWidth(1);
  
  if (table.getNumRows() > 0) {
    var headerRow = table.getRow(0);
    for (var j = 0; j < headerRow.getNumCells(); j++) {
      var cell = headerRow.getCell(j);
      cell.setBackgroundColor("#f0f4f9");
      var cellP = cell.getChild(0);
      if (cellP && cellP.getType() === DocumentApp.ElementType.PARAGRAPH) {
        cellP.asParagraph().setBold(true);
      }
    }
  }
  
  for (var r = 0; r < table.getNumRows(); r++) {
    var row = table.getRow(r);
    for (var c = 0; c < row.getNumCells(); c++) {
      var cell = row.getCell(c);
      var originalCellText = rows[r][c] || "";
      var cellP = cell.getChild(0);
      if (cellP && cellP.getType() === DocumentApp.ElementType.PARAGRAPH) {
        applyInlineStyles(cellP.asParagraph(), originalCellText);
      }
    }
  }
}

function cleanBold(text) {
  return text.replace(/\*\*(.*?)\*\*/g, "$1").replace(/\*(.*?)\*/g, "$1");
}

function applyInlineStyles(paragraph, rawText) {
  var regex = /\*\*(.*?)\*\*/g;
  var match;
  var cleanText = cleanBold(rawText);
  
  var lastIndex = 0;
  while ((match = regex.exec(rawText)) !== null) {
    var boldStr = match[1];
    var foundIndex = cleanText.indexOf(boldStr, lastIndex);
    if (foundIndex !== -1) {
      paragraph.editAsText().setBold(foundIndex, foundIndex + boldStr.length - 1, true);
      lastIndex = foundIndex + boldStr.length;
    }
  }
}
