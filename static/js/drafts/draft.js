var tps_valid_result = true;
window.onload = function () {
    if ($('tr').length){
        if ($('tr.table-active').length)
            dsao($('tr.table-active')[0])
        else{
            dsao($('tr.row')[1])
        }
    }
}

// выделение объекта dsao = draft select active object
function dsao(this_object) {
    if (this_object.parentElement.tagName !== 'THEAD') {
        $('tr.table-active').removeClass('table-active')
        this_object.className = 'row table-active'
        json_object = JSON.parse($('#json_object' + this_object.id).html())
        $('#s_timestamp').html(json_object['timestamp'])
        fill_object_form(false, true)
        if (get_path_from_url() === 'contract-draft')
            get_business_rule(true)
    }
}

// Вернуть сведения из истории - не используется
function retreive_draft_versions(json_object, is_contract=false) {
    let class_id = json_object.parent_structure
    let code = json_object.code
    let location = json_object.type
    if (json_object.type === 'array')
        location = (is_contract) ? 'contract' : 'table'

    $.ajax({url:'retreive-draft-versions',
        method:'get',
        dataType:'json',
        data: {class_id: class_id, code: code, location: location},
        success:function(data){
            // оформим таймлайн
            let quantity_events = (data.time_line.length - 1 < 0) ? 0 : data.time_line.length - 1
            let i_hist_range = $('#i_hist_range')
            let steplist = $('#steplist')
            steplist.html('')
            for (let i = 1; i <= quantity_events; i++){
                let op = document.createElement('option')
                op.innerText = i
                steplist.append(op)
            }
            i_hist_range.prop('max', quantity_events).val(quantity_events)
            // оформим файл истории
            $('#s_object_hist').html(JSON.stringify(data['object']))
            $('#s_time_line_list').html(JSON.stringify(data.time_line))
            $('span[id^="s_dict_hist_"]').remove() // Удалим массивы словарей
            // Создадим новые массивы истории словарей
            let parent_hist_dict = $('#s_object_hist').parent()
            for (let i = 0; i < data.dicts.length; i++){
                let dict_id = data.dicts[i].dict_id
                let dict_hist = document.createElement('span')
                dict_hist.id = 's_dict_hist_' + dict_id
                dict_hist.innerText = JSON.stringify(data.dicts[i].events)
                parent_hist_dict.append(dict_hist)
            }
            // заполним джейсон последним значением массивов истории
            moove_time()
        },
        error: function () {
            $('#s_object_hist').html('error')
        }
    })
}

// новый объект
function new_obj() {
    // чистим
    $('.table-active').removeClass('table-active')
    $('#i_code').val('')
    $('#i_id').val('')
    $("textarea[id*='ta_']").val('')
    $("input[id*='i_']").val('')
    $("input[id*='chb_']").attr('checked', false)
    $("span[id*='s_']").html('')
    $("div[id*='div_table_slave_']").html('')
    $('label[id*="l_file_"]').html('')
    $('div[id*="div_formula_"]').html('')
    $('#i_hist_range').val('').attr('max', '0')
    $('#steplist').html('')
    // Скрываем
    $("button[id*='b_save_']").attr('class', 'tag-invis')
    $("button[id*='b_del_']").attr('class', 'tag-invis')
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

// Новый черновик - отвязать от объекта
function draft_new() {
    // чистим
    $('.table-active').removeClass('table-active')
    $('#i_code').val('')
    $('#i_id').val('')
    // Если мы на черновике контракта, то дополнительно очистим поле "Дата и время записи"
    let url = window.location.href
    if (url.match(/contract-draft/)){
        let datetimerec_id = null
        let headers = $('span[id^="header_info"]')
        for (let i = 0; i < headers.length; i++){
            let json_obj = JSON.parse(headers[i].innerText)
            if (json_obj.name === 'Дата и время записи'){
                datetimerec_id = json_obj.id
                break
            }
        }
        $('#i_datetime_' + datetimerec_id).val('')
    }

}

// Показать расположение файла черновика
function show_file_loc_draft(header_id) {
    // надо впоймать активную строку и забрать айдишник
    let id = $('.table-active')[0].id
    let json_object = JSON.parse($('#json_object' + id).html())
    let filename = json_object[header_id].value
    if (filename){
        let root_folder = (window.location.href.match(/contract-draft/)) ? 'contract_' : 'table_'
        root_folder += json_object.parent_structure
        root_folder = 'database_files_draft/' + root_folder
        let date_folder = filename.slice(4, 8) + '-' + filename.slice(2, 4) + '-' + filename.slice(0, 2)
        let result = root_folder + '/' + date_folder + '/' + filename
        copyToClipboard(result)
        result += '\nскопировано в буфер обмена'
        alert(result)
    }
}


// Подсказка "Получатель"
function recepient_promp(){
    clearTimeout(typTimer);
    typTimer = setTimeout(()=>{
        let user_data = $('#i_recepient').val()
        let result = $('#dl_recepients')
        result.html('')
        $.ajax({url:'get-users',
            method:'get',
            dataType:'json',
            data: {user_data: user_data},
            success:function(data){
                data.forEach(e =>{
                    let op = document.createElement('option')
                    op.value = e.id
                    op.innerText = e.username + ' ' + e.first_name + ' ' + e.last_name
                    result.append(op)
                })
            },
            error: function () {}
        })
    }, 1000)
}

function recepient_on_span(){
    let user_id = $('#i_recepient').val()
    let array_users = $('#dl_recepients').children()
    for (let i = 0; i < array_users.length; i++){
        if (array_users[i].value === user_id){
            $('#s_recepient').text(array_users[i].innerText)
            break
        }
    }
}