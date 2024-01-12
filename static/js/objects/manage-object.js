window.onload = function () {
    let tr = $('#data-table tr')
    if (tr.length){
        // Если есть черновик - выводим его. Если нет, то актуальный / первый товар
        let table_active = $('#data-table tr.table-active')
        table_active.removeClass('table-active')
        let html_draft = $('#s_draft').html()
        if (html_draft)
            fill_draft(JSON.parse(html_draft))
        else if (table_active.length)
            sao(table_active[0], 't', true)
        else if (tr.length > 1)
            sao(tr[1], 't', true)
    }
    start_popovers()
}

function fill_draft(draft){
    $('#s_hist_range').html('Черновик').addClass('text-red')
    $('#i_hist_range').val('').attr('max', 0)
    $('#steplist').html('')
    let this_object = {}
    this_object.id = draft.code
    fill_object_form(draft, false, true)
    fill_dicts(draft)
}
// новый объект
function new_obj() {
    // чистим
    $('.table-active').removeClass('table-active')
    $('#i_code').val('')
    $("textarea[id*='ta_']").val('')
    $("input[id*='i_']").val('')
    $("input[id*='chb_']").attr('checked', false)
    $("span[id*='s_']").html('')
    $("div[id*='div_table_slave_']").html('')
    $('label[id*="l_file_"]').html('выберите файл')
    $('div[id*="div_formula_"]').html('')
    $('#i_hist_range').val('').attr('max', '0')
    $('#steplist').html('')
    $('#div_timeline_pagination').remove()
    // Скрываем
    $("button[id*='b_save_']").attr('class', 'tag-invis')
    $("button[id*='b_del_']").attr('class', 'tag-invis')
    $("button[id*='b_show_file_']").attr('class', 'tag-invis')
    // отобразим
    $('#b_save').attr('disabled', false)
    // заполним дефолты
    $("span[id*='header_info']").toArray().forEach((elem) => {
        let id = elem.id.slice(11)
        let dict = JSON.parse(elem.innerHTML)
        // вычислим префикс
        let pref = ''
        if (['string', 'eval'].includes(dict.formula))
            pref = 'ta_'
        else if (dict.formula === 'enum')
            pref = 's_enum_'
        else if (dict.formula === 'date')
            pref = 'i_date_'
        else if (dict.formula === 'datetime')
            pref = 'i_datetime_'
        else if (dict.formula === 'float')
            pref = 'i_float_'
        else if (dict.formula === 'link')
            pref = 'i_link_'
        else if (dict.formula === 'bool')
            pref = 'chb_'
        else if (dict.formula === 'const')
            pref = 's_alias_'
        // вставим данные
        let current_node = $('#' + pref + id)
        if (dict.formula === 'const'){
            current_node.children().attr('selected', false)
            for (let i = 0; i < current_node.children().length; i++){
                if (current_node.children()[i].value === dict.default){
                    current_node.children()[i].setAttribute('selected', true)
                    break
                }
            }
        }
        else if (dict.formula === 'bool')
            current_node.prop('checked', dict.default)
        else if (dict.formula === 'enum')
            current_node[0].selectedIndex = 0
        else current_node.val(dict.default)
        if (dict.formula === 'link')
            get_link_ajax(current_node[0])
        // Заполним собственника для массивов
        let owner = $('input[name="input_owner"]')
        if (owner.length){
            let id = $("a:contains('Собственник')")[0].id.slice(8)
            $('#i_link_' + id).val(owner[0].value)
        }
    })
    $('#div_wrapper_dicts').html('')  // Удалим словари
    $('[id*=dict_info]').val('')  // Удалим информацию о текущих словарях
    $('#div_footer_dict').attr('class', 'input-group mb-3')  // Откроем выпадающий список
    // Заполним выпадающий список
    let select = $('#new_dict')[0]
    if (select){
        select.innerHTML = ''
        let headers_dict = $('[id*="header_dict"]').toArray()
        headers_dict.forEach((e) => {
            let json_obj = JSON.parse(e.innerText)
            let op = document.createElement('option')
            op.value = json_obj.id
            op.innerText = json_obj.name
            select.appendChild(op)
        })
    }
    oe4no() // откроем факты для редактирования
}

