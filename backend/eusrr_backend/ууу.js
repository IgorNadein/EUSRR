// Проверяет наличие подписантов
function checkSubscribes() {
   let subscr = Подписанты || [], officFaces = Официальные_лица || [];
   for (let i = 0; i < subscr.length; i++) {
      if (subscr[i]['Подписанты.Должность'] || subscr[i]['Подписанты.Подпись']) {
         return true;
      }
   }
   for (let i = 0; i < officFaces.length; i++) {
      if (officFaces[i]['Официальные лица.ФИО'] || officFaces[i]['Официальные лица.Позиция'] || officFaces[i]['Официальные лица.Комментарий']) {
         return true;
      }
   }
   return false;
}

// Возвращает учетные характеристики ("КодПартии" из Генератор.ТабличныеДанные.ИнфПолСтр, строкой)
function get_nom_characteristics(info, charact) {
   var result = '',
      val,
      table = info;
   table.forEach(function(item) {
      if (item['Генератор.ТабличныеДанные.ИнфПол.Имя'].startsWith('КодПартии')) {
         val = item['Генератор.ТабличныеДанные.ИнфПол.Значение'] || '';
         result += ЭкранироватьHTML(val) + ' ';
      }
   });
   return result ? (', ' + result) : (charact ? (', ' + charact) : '');
}
// Возвращает примечание (Примечание из Генератор.ТабличныеДанные.ИнфПолСтр, строкой)
function get_nom_note(info) {
   var result = '';
   var table = info;
   var temp = '';
   table.forEach(function(item) {
      if (item['Генератор.ТабличныеДанные.ИнфПол.Имя'] === 'Примечание') {
         temp = item['Генератор.ТабличныеДанные.ИнфПол.Значение'];
         result += '\n' + ЭкранироватьHTML(temp.toString());
      }
   });
   return result ? result : '';
}
// Возвращает краткий состав комплекта (СоставКомплекта из Генератор.ТабличныеДанные.ИнфПолСтр, строкой)
function get_short_composition(info) {
   var table = info;
   var short_composition;
   var result = '';
   table.forEach(function(item) {
      if (item['Генератор.ТабличныеДанные.ИнфПол.Имя'] === 'СоставКомплекта') {
         short_composition = ЭкранироватьHTML(item['Генератор.ТабличныеДанные.ИнфПол.Значение'].toString());
         result = '\n' + short_composition;
      }
   });
   return result;
}
// Возвращает состав комплекта (СоставКомплектаПодробный из Генератор.ТабличныеДанные.ИнфПолСтр, вёрстка)
function get_full_composition(info, rnpt, date1, date2, flag1096) {
   var flagRnpt = rnpt;
   var dateDoc = new Date(date1);
   var dateStart = new Date(date2);
   var table = info;
   var full_composition = '';
   var nomenclature;
   var result = '';
   var result_rnpt = '';
   var row_number = 0;
   for (var i = 0; i < table.length; i++) {
      if (table[i]['Генератор.ТабличныеДанные.ИнфПол.Имя'] === 'СоставКомплектаПодробный') {
         full_composition = ЭкранироватьHTML(table[i]['Генератор.ТабличныеДанные.ИнфПол.Значение'].toString());
         break;
      }

   }
   if (full_composition) {
      full_composition = full_composition.split('##');
      let rowspan = full_composition.length;
      if (flagRnpt && (dateDoc > dateStart)) {
         for (let i = 0; i < rowspan; i++) {
            nomenclature = full_composition[i].split('#');
            row_number++;
            result += '<tr><td colspan=3 cstyle="EX2">' + row_number + '</td><td colspan=15 cstyle="EX1">' + ЭкранироватьHTML(nomenclature[0].toString()) +
               '</td><td colspan=8></td><td colspan=6 cstyle="EX3">' + ((nomenclature[1]) ? ФорматЧисло(nomenclature[1]) : '-') + '</td></tr>';
            if (i === 0) {
               if (flag1096) {
                  result_rnpt += '<tr><td colspan=3 cstyle="EX2">' + row_number + '</td><td colspan=15 cstyle="EX1">' + ЭкранироватьHTML(nomenclature[0].toString()) +
                  '</td><td colspan=8></td><td colspan=6 cstyle="EX3">' + ((nomenclature[1]) ? ФорматЧисло(nomenclature[1]) : '-')  +
                  '</td><td rowspan='  + rowspan + ' colspan=9></td><td rowspan=' + rowspan + ' colspan=31></td></tr>';
               } else {
                  result_rnpt += '<tr><td colspan=3 cstyle="EX2">' + row_number + '</td><td colspan=15 cstyle="EX1">' + ЭкранироватьHTML(nomenclature[0].toString()) +
                  '</td><td colspan=8></td><td colspan=6 cstyle="EX3">' + ((nomenclature[1]) ? ФорматЧисло(nomenclature[1]) : '-')  +
                  '</td><td rowspan='  + rowspan + ' colspan=12></td><td rowspan=' + rowspan + ' colspan=28></td></tr>';
               }
            } else {
               result_rnpt += '<tr><td colspan=3 cstyle="EX2">' + row_number + '</td><td colspan=15 cstyle="EX1">' + ЭкранироватьHTML(nomenclature[0].toString()) +
                  '</td><td colspan=8></td><td colspan=6 cstyle="EX3">' + ((nomenclature[1]) ? ФорматЧисло(nomenclature[1]) : '-') + '</td></tr>';
            }
         }
      } else if (dateDoc > dateStart) {
         for (let i = 0; i < rowspan; i++) {
            nomenclature = full_composition[i].split('#');
            row_number++;
            result += '<tr><td colspan=4 cstyle="EX2">' + row_number + '</td><td colspan=42 cstyle="EX1">' + ЭкранироватьHTML(nomenclature[0].toString()) +
               '</td><td colspan=8></td><td colspan=6 cstyle="EX3">' + ((nomenclature[1]) ? ФорматЧисло(nomenclature[1]) : '-') + '</td></tr>';
         }
      } else {
         for (let i = 0; i < rowspan; i++) {
            nomenclature = full_composition[i].split('#');
            row_number++;
            result += '<tr><td colspan=4 cstyle="EX2">' + row_number + '</td><td colspan=46 cstyle="EX1">' + ЭкранироватьHTML(nomenclature[0].toString()) +
               '</td><td colspan=8></td><td colspan=6 cstyle="EX3">' + ((nomenclature[1]) ? ФорматЧисло(nomenclature[1]) : '-') + '</td></tr>';
         }
      }
   }
   return {full_composition : result, full_composition_rnpt : result_rnpt, length : full_composition.length};
}
// Возвращает сумму НДС по формату
function get_vat_sum(vat_sum, tax_rate, wo_vat) {
   var result = '';
   if (vat_sum) {
      result = ФорматЧисло(parseFloat(vat_sum).toFixed(2));
   } else if (tax_rate === 'НДС исчисляется налоговым агентом') {
      result = '-';
   } else if (wo_vat === 'без НДС') {
      result = 'без НДС';
   } else {
      result = '0.00';
   }
   return result;

}
// Возвращает сумму по формату
function get_sum(sum, tax_rate) {
   var result = '0.00';
   if (sum) {
      result = ФорматЧисло(parseFloat(sum).toFixed(2));
   } else if (tax_rate === 'НДС исчисляется налоговым агентом') {
      result = '-';
   }
   return result;

}

// Построение таблицы номенклатуры
function mainTable(tableInfo) {
   var nom_array = tableInfo,
      body = '',
      total_price_sum_wo_vat = 0,
      total_vat_sum = 0,
      total_vat_sum_flag = true,
      total_sum = 0,
      row_number,name,charactTov,code,info,
      unit_code,
      unit,
      count,
      product_type,
      price_wo_vat,
      price_sum_wo_vat,
      excise,
      wo_excise,
      tax_rate,
      wo_vat,
      vat_sum,
      sum,
      country_code,
      country,
      declaration,
      full_composition,
      full_composition_rnpt,
      full_composition_length,
      rowspan,
      rowspanAddFields,
      flagRnpt = false,
      dateDoc = new Date(Генератор.Дата),
      dateStart = new Date('2021-06-30'),
      dateRes1096 = new Date('2024-09-30'),
      flagRes1096 = false,
      mainTableStr = '',
      totalTableStr = '',
      rowspanRnpt = '',
      rowspanRnptComp = '',
      footColspan2 = '7',
      startTable = '<table sstyles="EX1:EX12">',
      rnptResult = '',
      header = '',
      viewAddFields = Отобразить_дополнительные_поля,
      addFields = false,
      excepAddFields = ['КодПартии','Примечание','СоставКомплекта','СоставКомплектаПодробный','КодВидТов'];

   // Флаг для внесения правок в формы по постановлению 1096 для документов от 01.10.24
   if (dateDoc.setHours(0, 0, 0, 0) > dateRes1096.setHours(0, 0, 0, 0)) {
      flagRes1096 = true;
   }
   // Проверка на содержание прослеживаемых товаров в документе
   for (let i = 0; i < nom_array.length; i++) {
      if (nom_array[i]['Генератор.ТабличныеДанные.RnptData'].length) {
         flagRnpt = true;
         break;
      }
   }
   startTable += '<col width=8>'.repeat(152);
   // Для документов от 01.07.2021 с прослеживаемыми товарами добавляется 3 столбца
   if (flagRnpt && (dateDoc > dateStart)) {
      //Формирование шапки таблицы
      if (flagRes1096) {
         header += startTable + '<tr cstyle="EX11"><td rowspan=4 colspan=13 cstyle="EX12">Код товара/\nработ,услуг</td><td rowspan=4 colspan=4>№\nп/п</td><td rowspan=4 colspan=18>Наименование товара\n(описание выполненных работ, оказанных услуг),\nимущественного права</td><td rowspan=4 colspan=5>Код\nвида\nтова-\nра</td><td colspan=11 rowspan=1>Единица\nизмерения</td><td rowspan=4 colspan=6>Коли-\nчество\n(объем)</td><td rowspan=4 colspan=7>Цена, (тариф) за единицу измере-\nния</td>';
         header += '<td rowspan=4 colspan=9>Стоимость товаров (работ, услуг), имуществен-\nных прав без налога - всего</td><td rowspan=4 colspan=5>В том числе сумма акциза</td><td rowspan=4 colspan=5>Нало-\nговая\nставка</td><td rowspan=4 colspan=8>Сумма налога,предъявля-\nемая покупа-\nтелю</td><td rowspan=4 colspan=9>Стоимость товаров (работ, услуг), имуществен-\nных прав с налогом - всего</td><td colspan=12 rowspan=2>Страна происхождения товара</td>';
         header += '<td rowspan=4 colspan=9>Регистрационный номер декларации на товары или регистрационный номер партии товара, подлежащего прослеживаемости</td><td colspan=10 rowspan=3>Количественная единица измерения товара, используемая в целях осуществления прослеживаемости</td><td rowspan=4 colspan=11>Количество товара, подлежащего прослеживаемости, в количественной единице измерения товара, используемой в целях осуществления прослеживаемости</td>';
         header += '<td rowspan=4 colspan=10>Стоимость товара, подлежащего прослеживаемости, без налога на добавленную стоимость, в рублях</td></tr>';
         header += '<tr cstyle="EX11"><td rowspan=3 colspan=3>код</td><td rowspan=3 colspan=8>условное\nобозначе-\nние (националь-\nное)</td></tr><tr cstyle="EX11"><td rowspan=2 colspan=5>Цифро-\nвой код</td><td rowspan=2 colspan=7>Краткое наимено-\nвание</td></tr><tr cstyle="EX11"><td rowspan=1 colspan=3>код</td><td rowspan=1 colspan=7>условное\nобозначение</td></tr>';
         header += '<tr cstyle="EX4"><td colspan=13 cstyle="EX6">А</td><td colspan=4>1</td><td colspan=18>1а</td><td colspan=5>1б</td><td colspan=3>2</td><td colspan=8>2а</td><td colspan=6>3</td><td colspan=7>4</td><td colspan=9>5</td><td colspan=5>6</td><td colspan=5>7</td><td colspan=8>8</td><td colspan=9>9</td><td colspan=5>10</td><td colspan=7>10а</td><td colspan=9>11</td><td colspan=3>12</td><td colspan=7>12а</td><td colspan=11>13</td><td colspan=10>14</td></tr>';
      } else {
         header += startTable + '<tr cstyle="EX4"><td rowspan=4 colspan=13 cstyle="EX6">Код товара/\nработ,услуг</td><td rowspan=4 colspan=4>№\nп/п</td><td rowspan=4 colspan=18>Наименование товара\n(описание выполненных работ, оказанных услуг),\nимущественного права</td><td rowspan=4 colspan=5>Код\nвида\nтова-\nра</td><td colspan=11 rowspan=1>Единица\nизмерения</td><td rowspan=4 colspan=6>Коли-\nчество\n(объем)</td><td rowspan=4 colspan=7>Цена, (тариф) за единицу измере-\nния</td>';
         header += '<td rowspan=4 colspan=9>Стоимость товаров (работ, услуг), имуществен-\nных прав без налога - всего</td><td rowspan=4 colspan=5>В том числе сумма акциза</td><td rowspan=4 colspan=5>Нало-\nговая\nставка</td><td rowspan=4 colspan=8>Сумма налога,предъявля-\nемая покупа-\nтелю</td><td rowspan=4 colspan=9>Стоимость товаров (работ, услуг), имуществен-\nных прав с налогом - всего</td><td colspan=12 rowspan=2>Страна происхождения товара</td>';
         header += '<td rowspan=4 colspan=12>Регистрационный номер декларации на товары или регистрационный номер партии товара, подлежащего прослеживаемости</td><td colspan=13 rowspan=3>Количественная единица измерения товара, используемая в целях осуществления прослеживаемости</td><td rowspan=4 colspan=15>Количество товара, подлежащего прослеживаемости, в количественной единице измерения товара, используемой в целях осуществления прослеживаемости</td></tr>';
         header += '<tr cstyle="EX4"><td rowspan=3 colspan=3>код</td><td rowspan=3 colspan=8>условное\nобозначе-\nние (националь-\nное)</td></tr><tr cstyle="EX4"><td rowspan=2 colspan=5>Цифро-\nвой код</td><td rowspan=2 colspan=7>Краткое наимено-\nвание</td></tr><tr cstyle="EX4"><td rowspan=1 colspan=4>код</td><td rowspan=1 colspan=9>условное\nобозначение</td></tr>';
         header += '<tr cstyle="EX4"><td colspan=13 cstyle="EX6">А</td><td colspan=4>1</td><td colspan=18>1а</td><td colspan=5>1б</td><td colspan=3>2</td><td colspan=8>2а</td><td colspan=6>3</td><td colspan=7>4</td><td colspan=9>5</td><td colspan=5>6</td><td colspan=5>7</td><td colspan=8>8</td><td colspan=9>9</td><td colspan=5>10</td><td colspan=7>10а</td><td colspan=12>11</td><td colspan=4>12</td><td colspan=9>12а</td><td colspan=15>13</td></tr>';
      }
      footColspan2 = '51';
   } else if (dateDoc > dateStart) {
      //Формирование шапки таблицы
      header += startTable + '<tr cstyle="EX4"><td rowspan=4 colspan=13 cstyle="EX6">Код товара/\nработ,услуг</td><td rowspan=4 colspan=4>№\nп/п</td><td rowspan=4 colspan=46>Наименование товара\n(описание выполненных работ, оказанных услуг),\nимущественного права</td><td rowspan=4 colspan=5>Код\nвида\nтова-\nра</td><td colspan=11 rowspan=1>Единица\nизмерения</td><td rowspan=4 colspan=6>Коли-\nчество\n(объем)</td><td rowspan=4 colspan=7>Цена, (тариф) за единицу измере-\nния</td>';
      header += '<td rowspan=4 colspan=9>Стоимость товаров (работ, услуг), имуществен-\nных прав без налога - всего</td><td rowspan=4 colspan=5>В том числе сумма акциза</td><td rowspan=4 colspan=5>Нало-\nговая\nставка</td><td rowspan=4 colspan=8>Сумма налога,предъявля-\nемая покупа-\nтелю</td><td rowspan=4 colspan=9>Стоимость товаров (работ, услуг), имуществен-\nных прав с налогом - всего</td><td colspan=12 rowspan=2>Страна происхождения товара</td>';
      header += '<td rowspan=4 colspan=12>Регистрационный номер декларации на товары или регистрационный номер партии товара, подлежащего прослеживаемости</td></tr><tr cstyle="EX4"><td rowspan=3 colspan=3>код</td><td rowspan=3 colspan=8>условное\nобозначе-\nние (националь-\nное)</td></tr><tr cstyle="EX4"><td rowspan=2 colspan=5>Цифро-\nвой код</td><td rowspan=2 colspan=7>Краткое наимено-\nвание</td></tr>';
      header += '<tr cstyle="EX4"></tr><tr cstyle="EX4"><td colspan=13 cstyle="EX6">А</td><td colspan=4>1</td><td colspan=46>1а</td><td colspan=5>1б</td><td colspan=3>2</td><td colspan=8>2а</td><td colspan=6>3</td><td colspan=7>4</td><td colspan=9>5</td><td colspan=5>6</td><td colspan=5>7</td><td colspan=8>8</td><td colspan=9>9</td><td colspan=5>10</td><td colspan=7>10а</td><td colspan=12>11</td></tr>';
      footColspan2 = '79';
   } else {
      //Формирование шапки таблицы
      header += startTable + '<tr cstyle="EX4"><td rowspan=4 colspan=4>№\nп/п</td><td rowspan=4 colspan=9 cstyle="EX6">Код товара/\nработ,услуг</td><td rowspan=4 colspan=50>Наименование товара\n(описание выполненных работ, оказанных услуг),\nимущественного права</td><td rowspan=4 colspan=5>Код\nвида\nтова-\nра</td><td colspan=11 rowspan=1>Единица\nизмерения</td><td rowspan=4 colspan=6>Коли-\nчество\n(объем)</td><td rowspan=4 colspan=7>Цена, (тариф) за единицу измере-\nния</td>';
      header += '<td rowspan=4 colspan=9>Стоимость товаров (работ, услуг), имуществен-\nных прав без налога - всего</td><td rowspan=4 colspan=5>В том числе сумма акциза</td><td rowspan=4 colspan=5>Нало-\nговая\nставка</td><td rowspan=4 colspan=8>Сумма налога,предъявля-\nемая покупа-\nтелю</td><td rowspan=4 colspan=9>Стоимость товаров (работ, услуг), имуществен-\nных прав с налогом - всего</td><td colspan=12 rowspan=2>Страна происхождения товара</td>';
      header += '<td rowspan=4 colspan=12>Регистрационный номер декларации на товары или регистрационный номер партии товара, подлежащего прослеживаемости</td></tr><tr cstyle="EX4"><td rowspan=3 colspan=3>код</td><td rowspan=3 colspan=8>условное\nобозначе-\nние (националь-\nное)</td></tr><tr cstyle="EX4"><td rowspan=2 colspan=5>Цифро-\nвой код</td><td rowspan=2 colspan=7>Краткое наимено-\nвание</td></tr>';
      header += '<tr cstyle="EX4"></tr><tr cstyle="EX4"><td colspan=4 cstyle="EX4">А</td><td cstyle="EX6" colspan=9>Б</td><td colspan=50>1</td><td colspan=5>1а</td><td colspan=3>2</td><td colspan=8>2а</td><td colspan=6>3</td><td colspan=7>4</td><td colspan=9>5</td><td colspan=5>6</td><td colspan=5>7</td><td colspan=8>8</td><td colspan=9>9</td><td colspan=5>10</td><td colspan=7>10а</td><td colspan=12>11</td></tr>';
      footColspan2 = '79';
   }

   //Формирование основной части таблицы
   nom_array.forEach(function(nom) {
      //инициализация полей
      row_number = nom['Генератор.ТабличныеДанные.ПорНомер'];
      name = nom['Генератор.ТабличныеДанные.Наименование'];
      charactTov = nom['Генератор.ТабличныеДанные.КодПартии'] || '';
      code = nom['Генератор.ТабличныеДанные.НомНомер'] || '-';
      info = nom['Генератор.ТабличныеДанные.ИнфПол'];
      unit_code = nom['Генератор.ТабличныеДанные.ЕдКод'] || '-';
      unit = nom['Генератор.ТабличныеДанные.ЕдИзм'] || '-';
      if (unit.indexOf('^') >= 0) {
         unit = unit.replace(/\^(\d+)/g, '$1').replace(/\^/g, '');
      }
      count = nom['Генератор.ТабличныеДанные.Количество'];
      if (count) {
         count = (count < 1) ? ЭкспоненциальнаяВЧислоСтрокой(count) : ФорматЧисло(count);
      } else {
         count = '-';
      }
      product_type = nom['Генератор.ТабличныеДанные.КодВидТов'] ? ЭкранироватьHTML(nom['Генератор.ТабличныеДанные.КодВидТов'].toString()) : '-';
      price_wo_vat = nom['Генератор.ТабличныеДанные.ЦенаБезНДС'];
      price_sum_wo_vat = nom['Генератор.ТабличныеДанные.СуммаЦенБезНДС'];
      excise = nom['Генератор.ТабличныеДанные.Акциз'];
      wo_excise = nom['Генератор.ТабличныеДанные.БезАкциз'];
      tax_rate = nom['Генератор.ТабличныеДанные.НДСЗначение'];
      wo_vat = nom['Генератор.ТабличныеДанные.БезНДС'];
      vat_sum = nom['Генератор.ТабличныеДанные.СуммаНДС'];
      sum = nom['Генератор.ТабличныеДанные.СуммаЦен'];
      country_code = nom['Генератор.ТабличныеДанные.КодСтраныПроизводства'] || '-';
      country_code = (country_code === '643') ? '-' : country_code;
      country = nom['Генератор.ТабличныеДанные.СтранаПроизводства'];
      country = (country === 'РОССИЯ') ? '-' : country;
      declaration = nom['Генератор.ТабличныеДанные.ГТД'] || '-';
      full_composition = get_full_composition(info, flagRnpt, dateDoc, dateStart, flagRes1096);
      full_composition_length = full_composition.length;
      full_composition_rnpt = full_composition.full_composition_rnpt;
      full_composition = full_composition.full_composition;
      rowspan = (full_composition) ? ('rowspan=' + (full_composition_length + 1)) : ' ';

      let addFieldsArray = [],
         addFiledsStr = '';
      addFields = false;
      if (viewAddFields) {
         for (let i = 0; i < info.length; i++) {
            if (!excepAddFields.includes(info[i]['Генератор.ТабличныеДанные.ИнфПол.Имя'])) {
               addFieldsArray.push(info[i]['Генератор.ТабличныеДанные.ИнфПол.Имя'] + ': ' + ЭкранироватьHTML((info[i]['Генератор.ТабличныеДанные.ИнфПол.Значение'] || '').replace(/\n/g, ' ')));
            }
         }
         if (addFieldsArray.length) {
            addFields = true;
         }
      }

      // Для документов от 01.07.2021 с прослеживаемыми товарами добавляется 3 столбца
      rnptResult = '';
      mainTableStr = '';
      rowspanRnpt = '';
      rowspanRnptComp = '';
      if (flagRnpt && (dateDoc > dateStart)) {
         let rnptData = nom['Генератор.ТабличныеДанные.RnptData'];
         let rnptRowspan = 1;
         if (rnptData.length) {
            let rnptRow01 = rnptData[0]['Генератор.ТабличныеДанные.RnptData.Rnpt'] ? rnptData[0]['Генератор.ТабличныеДанные.RnptData.Rnpt'] : '-',
               rnptRow02 = rnptData[0]['Генератор.ТабличныеДанные.RnptData.MuCode'] ? rnptData[0]['Генератор.ТабличныеДанные.RnptData.MuCode'] : '-',
               rnptRow03 = rnptData[0]['Генератор.ТабличныеДанные.RnptData.MuName'] ? rnptData[0]['Генератор.ТабличныеДанные.RnptData.MuName'] : '-',
               rnptRow04 = rnptData[0]['Генератор.ТабличныеДанные.RnptData.RnptQty'] ? rnptData[0]['Генератор.ТабличныеДанные.RnptData.RnptQty'] : '-';
            if (flagRes1096) {
               let rnptRow05 = rnptData[0]['Генератор.ТабличныеДанные.RnptData.SumCostWoVat'] ? parseFloat(rnptData[0]['Генератор.ТабличныеДанные.RnptData.SumCostWoVat']).toFixed(2) : '0';
               mainTableStr = '<td colspan=9 cstyle="EX2">' + rnptRow01 + '</td><td colspan=3 cstyle="EX2">' + rnptRow02 + '</td><td colspan=7 cstyle="EX2">' + rnptRow03 + '</td><td colspan=11 cstyle="EX2">' + rnptRow04 + '</td><td colspan=10 cstyle="EX2">' + rnptRow05 + '</td>';
            } else {
               mainTableStr = '<td colspan=12 cstyle="EX2">' + rnptRow01 + '</td><td colspan=4 cstyle="EX2">' + rnptRow02 + '</td><td colspan=9 cstyle="EX2">' + rnptRow03 + '</td><td colspan=15 cstyle="EX2">' + rnptRow04 + '</td>';
            }
            rnptRowspan = rnptData.length;

            for (let i = 1; i < rnptData.length; i++) {
               let rnptRow1 = rnptData[i]['Генератор.ТабличныеДанные.RnptData.Rnpt'] ? rnptData[i]['Генератор.ТабличныеДанные.RnptData.Rnpt'] : '-',
                  rnptRow2 = rnptData[i]['Генератор.ТабличныеДанные.RnptData.MuCode'] ? rnptData[i]['Генератор.ТабличныеДанные.RnptData.MuCode'] : '-',
                  rnptRow3 = rnptData[i]['Генератор.ТабличныеДанные.RnptData.MuName'] ? rnptData[i]['Генератор.ТабличныеДанные.RnptData.MuName'] : '-',
                  rnptRow4 = rnptData[i]['Генератор.ТабличныеДанные.RnptData.RnptQty'] ? rnptData[i]['Генератор.ТабличныеДанные.RnptData.RnptQty'] : '-';
               if (flagRes1096) {
                  let rnptRow5 = rnptData[i]['Генератор.ТабличныеДанные.RnptData.SumCostWoVat'] ? parseFloat(rnptData[i]['Генератор.ТабличныеДанные.RnptData.SumCostWoVat']).toFixed(2) : '0';
                  rnptResult += '<tr><td colspan=9 cstyle="EX2">' + rnptRow1 + '</td><td colspan=3 cstyle="EX2">' + rnptRow2 + '</td><td colspan=7 cstyle="EX2">' + rnptRow3 + '</td><td colspan=11 cstyle="EX2">' + rnptRow4 + '</td><td colspan=10 cstyle="EX2">' + rnptRow5 + '</td>';
               } else {
                  rnptResult += '<tr><td colspan=12 cstyle="EX2">' + rnptRow1 + '</td><td colspan=4 cstyle="EX2">' + rnptRow2 + '</td><td colspan=9 cstyle="EX2">' + rnptRow3 + '</td><td colspan=15 cstyle="EX2">' + rnptRow4 + '</td>';
               }
               rnptResult += '</tr>';
            }
         } else {
            if (flagRes1096) {
               mainTableStr = '<td colspan=9 cstyle="EX2">' + (declaration ? declaration : '-') + '</td><td colspan=3 cstyle="EX2">-</td><td colspan=7 cstyle="EX2">-</td><td colspan=11 cstyle="EX2">-</td><td colspan=10 cstyle="EX2">-</td>';
            } else {
               mainTableStr = '<td colspan=12 cstyle="EX2">' + (declaration ? declaration : '-') + '</td><td colspan=4 cstyle="EX2">-</td><td colspan=9 cstyle="EX2">-</td><td colspan=15 cstyle="EX2">-</td>';
            }
         }
         rowspanRnpt = 'rowspan=' + rnptRowspan;
         rowspanRnptComp = 'rowspan=' + (rnptRowspan + full_composition_length);
         if (flagRes1096) {
            totalTableStr = '<td colspan=3 cstyle="EX8"></td><td colspan=7 cstyle="EX8"></td><td colspan=11 cstyle="EX8"></td><td colspan=10 cstyle="EX8"></td>';
         } else {
            totalTableStr = '<td colspan=4 cstyle="EX8"></td><td colspan=9 cstyle="EX8"></td><td colspan=15 cstyle="EX8"></td>';
         }

         // расчет допполей
         if (!addFields) {
            rowspanAddFields = rowspanRnptComp;
         } else {
            rowspanAddFields = 'rowspan=' + (rnptRowspan + full_composition_length + 1);
            addFiledsStr = '<tr><td colspan=135>' + addFieldsArray.join(', ') + '</td></tr>';
         }

         //Формирование тела таблицы в документе с прослеживаемостью
         body += '<tr><td ' + rowspanAddFields + ' colspan=13 cstyle="EX7">' + ЭкранироватьHTML(code.toString()) + '</td><td ' + rowspanAddFields + ' colspan=4 cstyle="EX2">' + row_number + '</td><td ' + rowspanRnpt + ' colspan=18 cstyle="EX1">' + ЭкранироватьHTML(name.toString()) + get_nom_characteristics(info, charactTov) + get_nom_note(info) + get_short_composition(info) + '</td>';
         body += '<td ' + rowspanRnptComp + ' colspan=5 cstyle="EX2">' + product_type + '</td><td ' + rowspanRnptComp + ' colspan=3 cstyle="EX2">' + unit_code + '</td><td ' + rowspanRnpt + ' colspan=8 cstyle="EX2">' + unit + '</td><td ' + rowspanRnpt + ' colspan=6 cstyle="EX3">' + count + '</td><td ' + rowspanRnptComp + ' colspan=7 cstyle="EX3">' + (price_wo_vat ? ФорматЧисло(parseFloat(price_wo_vat).toFixed(2)) : '-') + '</td>';
         body += '<td ' + rowspanRnptComp + ' colspan=9 cstyle="EX3">' + (price_sum_wo_vat ? ФорматЧисло(parseFloat(price_sum_wo_vat).toFixed(2)) : '-') + '</td><td ' + rowspanRnptComp + ' colspan=5 cstyle="EX2">' + ((wo_excise === 'без акциза') ? 'без акциза' : ((excise) ? ФорматЧисло(parseFloat(excise).toFixed(2)) : '0.00')) + '</td><td ' + rowspanRnptComp + ' colspan=5 cstyle="EX2">' + (tax_rate ? tax_rate : '-') + '</td>';
         body += '<td ' + rowspanRnptComp + ' colspan=8 cstyle="EX3">' + get_vat_sum (vat_sum, tax_rate, wo_vat) + '</td><td ' + rowspanRnptComp + ' colspan=9 cstyle="EX3">' + get_sum(sum, tax_rate) + '</td><td ' + rowspanRnptComp + ' colspan=5 cstyle="EX2">' + (country_code ? country_code : '-') + '</td><td ' + rowspanRnptComp + ' colspan=7 cstyle="EX2">' + (country ? country : '-') + '</td>' + mainTableStr + '</tr>' + rnptResult + full_composition_rnpt + addFiledsStr;
      } else if (dateDoc > dateStart) {

         // расчет допполей
         if (!addFields) {
            rowspanAddFields = rowspan;
         } else {
            rowspanAddFields = (full_composition) ? ('rowspan=' + (full_composition_length + 2)) : 'rowspan=2';
            addFiledsStr = '<tr><td colspan=135>' + addFieldsArray.join(', ') + '</td></tr>';
         }

         //Формирование тела таблицы в документе без прослеживаемости
         body += '<tr><td ' + rowspanAddFields + ' colspan=13 cstyle="EX7">' + ЭкранироватьHTML(code.toString()) + '</td><td ' + rowspanAddFields + ' colspan=4 cstyle="EX2">' + row_number + '</td><td colspan=46 cstyle="EX1">' + ЭкранироватьHTML(name.toString()) + get_nom_characteristics(info, charactTov) + get_nom_note(info) + get_short_composition(info) + '</td><td ' + rowspan + ' colspan=5 cstyle="EX2">' + product_type + '</td>';
         body += '<td ' + rowspan + ' colspan=3 cstyle="EX2">' + unit_code + '</td><td colspan=8 cstyle="EX2">' + unit + '</td><td colspan=6 cstyle="EX3">' + count + '</td><td ' + rowspan + ' colspan=7 cstyle="EX3">' + (price_wo_vat ? ФорматЧисло(parseFloat(price_wo_vat).toFixed(2)) : '-') + '</td><td ' + rowspan + ' colspan=9 cstyle="EX3">' + (price_sum_wo_vat ? ФорматЧисло(parseFloat(price_sum_wo_vat).toFixed(2)) : '-') + '</td>';
         body += '<td ' + rowspan + ' colspan=5 cstyle="EX2">' + ((wo_excise === 'без акциза') ? 'без акциза' : ((excise) ? ФорматЧисло(parseFloat(excise).toFixed(2)) : '0.00')) + '</td><td ' + rowspan + ' colspan=5 cstyle="EX2">' + (tax_rate ? tax_rate : '-') + '</td><td ' + rowspan + ' colspan=8 cstyle="EX3">' + get_vat_sum (vat_sum, tax_rate, wo_vat) + '</td><td ' + rowspan + ' colspan=9 cstyle="EX3">' + get_sum(sum, tax_rate) + '</td>';
         body += '<td ' + rowspan + ' colspan=5 cstyle="EX2">' + (country_code ? country_code : '-') + '</td><td ' + rowspan + ' colspan=7 cstyle="EX2">' + (country ? country : '-') + '</td><td ' + rowspan + ' colspan=12>' + (declaration ? declaration : '-') + '</td></tr>' + full_composition + addFiledsStr;
      } else {

         // расчет допполей
         if (!addFields) {
            rowspanAddFields = rowspan;
         } else {
            rowspanAddFields = (full_composition) ? ('rowspan=' + (full_composition_length + 2)) : 'rowspan=2';
            addFiledsStr = '<tr><td colspan=139>' + addFieldsArray.join(', ') + '</td></tr>';
         }

         //Формирование тела таблицы в документе без прослеживаемости
         body += '<tr><td ' + rowspanAddFields + ' colspan=4 cstyle="EX2">' + row_number + '</td><td ' + rowspanAddFields + ' colspan=9 cstyle="EX7">' + ЭкранироватьHTML(code.toString()) + '</td><td colspan=50 cstyle="EX1">' + ЭкранироватьHTML(name.toString()) + get_nom_characteristics(info, charactTov) + get_nom_note(info) + get_short_composition(info) + '</td><td ' + rowspan + ' colspan=5 cstyle="EX2">' + product_type + '</td>';
         body += '<td ' + rowspan + ' colspan=3 cstyle="EX2">' + unit_code + '</td><td colspan=8 cstyle="EX2">' + unit + '</td><td colspan=6 cstyle="EX3">' + count + '</td><td ' + rowspan + ' colspan=7 cstyle="EX3">' + (price_wo_vat ? ФорматЧисло(parseFloat(price_wo_vat).toFixed(2)) : '-') + '</td><td ' + rowspan + ' colspan=9 cstyle="EX3">' + (price_sum_wo_vat ? ФорматЧисло(parseFloat(price_sum_wo_vat).toFixed(2)) : '-') + '</td>';
         body += '<td ' + rowspan + ' colspan=5 cstyle="EX2">' + ((wo_excise === 'без акциза') ? 'без акциза' : ((excise) ? ФорматЧисло(parseFloat(excise).toFixed(2)) : '0.00')) + '</td><td ' + rowspan + ' colspan=5 cstyle="EX2">' + (tax_rate ? tax_rate : '-') + '</td><td ' + rowspan + ' colspan=8 cstyle="EX3">' + get_vat_sum (vat_sum, tax_rate, wo_vat) + '</td><td ' + rowspan + ' colspan=9 cstyle="EX3">' + get_sum(sum, tax_rate) + '</td>';
         body += '<td ' + rowspan + ' colspan=5 cstyle="EX2">' + (country_code ? country_code : '-') + '</td><td ' + rowspan + ' colspan=7 cstyle="EX2">' + (country ? country : '-') + '</td><td ' + rowspan + ' colspan=12>' + (declaration ? declaration : '-') + '</td></tr>' + full_composition + addFiledsStr;
      }

      //расчет итоговых параметров
      total_price_sum_wo_vat += price_sum_wo_vat ? parseFloat(price_sum_wo_vat) : 0;
      total_vat_sum += vat_sum ? parseFloat(vat_sum) : 0;
      if (total_vat_sum_flag) {
         total_vat_sum_flag = wo_vat === 'без НДС';
      }
      total_sum += sum ? parseFloat(sum) : 0;
   });

   //Формирование подвала таблицы
   body += '<tr><td colspan=13 cstyle="EX9"></td><td colspan=' + footColspan2 + ' cstyle="EX5">Всего к оплате</td><td colspan=9 cstyle="EX3">' + ФорматЧисло(total_price_sum_wo_vat.toFixed(2)) + '</td><td colspan=10 cstyle="EX2">X</td><td colspan=8 cstyle="EX3">' + (total_vat_sum_flag ? 'без НДС' : ФорматЧисло(total_vat_sum.toFixed(2))) + '</td>';
   if (flagRes1096) {
      body += '<td colspan=9 cstyle="EX3">' + ФорматЧисло(total_sum.toFixed(2)) + '</td><td colspan=5 cstyle="EX8"></td><td colspan=7 cstyle="EX8"></td><td colspan=9 cstyle="EX8"></td>' + totalTableStr + '</tr>';
   } else {
      body += '<td colspan=9 cstyle="EX3">' + ФорматЧисло(total_sum.toFixed(2)) + '</td><td colspan=5 cstyle="EX8"></td><td colspan=7 cstyle="EX8"></td><td colspan=12 cstyle="EX8"></td>' + totalTableStr + '</tr>';
   }

   return (header + body + '</table>');
}