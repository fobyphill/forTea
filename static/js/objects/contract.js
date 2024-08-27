// Переменные для таймера запуска аякса
var typingTimer;
var contract_biz_rule = true


window.onload = function () {
    let tr = $('#data-table tr')
    if (tr.length){
        let table_active = $('#data-table tr.table-active')
        table_active.removeClass('table-active')
        if (table_active.length)
            // select_active_object(table_active[0])
            sao(table_active[0], 'c', true)
        else if (tr.length > 1)
            sao(tr[1], 'c', true)
    }
    start_popovers()
    fill_search_filter()  // Заполним фильтры поиска
}

// новый объект
function new_obj() {
    // чистим
    $('.table-active').removeClass('table-active')
    $('#i_code').val('')
    $('input[id*="date_time_record"]').val('')
    $("textarea[id*='ta_']").val('')
    $("input[id*='i_']").val('')
    $("input[id*='chb_']").attr('checked', false)
    $("span[id*='s_']").html('')
    $('label[id*="l_file_"]').html('Выберите файл')
    $('div[id*="div_formula_"]').html('')
    $("div[id*='div_table_slave_']").html('')
    $('#i_hist_range').val('').attr('max', '0')
    $('#steplist').html('')
    $('#div_timeline_pagination').remove()
    // чистим JSON-object
    for (let json_key in json_object){
        if (parseInt(json_key)){
            if ('value' in json_object[json_key])
                json_object[json_key].value = null
            if ('delay' in json_object[json_key])
                json_object[json_key].delay = null
        }
    }
    // Скрываем
    $("button[id*='b_save_']").attr('class', 'tag-invis')
    $("button[id*='b_del_']").attr('class', 'tag-invis')
    $('#div_tl_delay').attr('class', 'tag-invis')
    // покажем
    $('#b_save').attr('disabled', false)
    // Разблочим собственника
    let owner = $('a:contains("Собственник")')
    if (owner.length){
        let owner_id = owner[0].id.slice(8)
        $('#i_link_' + owner_id).attr('readonly', false).css('background-color', 'white')
    }
    // Получим техпроцессы
    tps = JSON.parse($('#tps').text())
    // Получим контрольные поля для техпроцессов
    let cfs = []
    tps.forEach(el => cfs.push(el.cf))
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
            current_node.prop('checked', (dict.default === 'True'))
        else if (dict.formula === 'enum')
            current_node[0].selectedIndex = 0
        else if (dict.formula === 'float'){
            current_node.val(dict.default)
            // Если данное поле является контрольным для техпроцессов - то запустим калькулятор ТПов
            if (tps.length && tps[0].control_field === parseInt(id)){
                $('input[id^="i_stage_"]').attr('readonly', true).val('')
                tps.forEach((el) => rfsot(current_node[0]))
            }
            if (cfs.includes(parseInt(id))){
                $('input[id^="i_stage_"]').attr('readonly', true).val('')
                reflofi(current_node[0], true)
            }
        }
        else current_node.val(dict.default)
        if (dict.formula === 'link')
            fast_get_link(current_node[0], 'c')
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
    if (select)
        select.innerHTML = ''
    let headers_dict = $('[id*="header_dict"]').toArray()
    headers_dict.forEach((e) => {
        let json_obj = JSON.parse(e.innerText)
        let op = document.createElement('option')
        op.value = json_obj.id
        op.innerText = json_obj.name
        select.appendChild(op)
    })
    // изничтожим данные техпроцессов
    $('span[id^="s_stage_"]').html('')

}

function recount_tps(this_inp, is_set_interval=false) {
    let interval = (is_set_interval) ? 1000 : 0
    clearTimeout(typingTimer);
    typingTimer = setInterval(() => {
        let sum = (this_inp.value) ? parseFloat(this_inp.value) : 0
        let field_id = parseInt(this_inp.id.slice(8))
        let tps = JSON.parse($('#tps').text())
        // Проверим величину возврата
        let max_return = 0
        tps.forEach((el) => {
            if (el.cf_val === field_id){
                let current_sum = get_tp_currrent_sum(el.id)
                if (sum !== current_sum){
                    let delta = sum - current_sum
                    let first_stage = $('#i_stage_' + el.id + '_0')
                    let old_val = (first_stage.val()) ? parseFloat(first_stage.val()) : 0
                    let new_val = old_val + delta
                    if (new_val < 0){
                        delta_return = new_val * -1
                        if (delta_return > max_return)
                            max_return = delta_return
                    }
                }
            }
        })
        // Изменим первые стадии техпроцессов с учетом поправки вычитаемой суммы
        sum += max_return
        tps.forEach((el) => {
            if (el.cf_val === field_id){
                let current_sum = get_tp_currrent_sum(el.id)
                if (sum !== current_sum){
                    let delta = sum - current_sum
                    let first_stage = $('#i_stage_' + el.id + '_0')
                    let old_val = (first_stage.val()) ? parseFloat(first_stage.val()) : 0
                    first_stage.val(old_val + delta)
                    let first_delay = $('#s_stage_' + el.id + '_0_delay')
                    let old_delay = (first_delay.text()) ? parseFloat(first_delay.text()) : 0
                    first_delay.text(old_delay + delta)
                }
            }
        })
        this_inp.value = sum
    }, interval)
}

function get_tp_currrent_sum(tp_id) {
    let tag_stages = $('input[id^="i_stage_' + tp_id + '_"]').toArray()
    let current_sum = 0
    tag_stages.forEach((el) => {
        current_sum += (el.value) ? parseFloat(el.value) : 0
    })
    return current_sum
}






