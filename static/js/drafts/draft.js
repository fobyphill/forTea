var tps_valid_result = true;
var timer_link
var tps


window.onload = function () {
    if ($('tr.row').length > 1){
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
        let is_contract = (get_path_from_url() === 'contract-draft')
        if (is_contract)
            fill_tps(json_object)
        fill_object_form(is_contract, true)
        if (is_contract)
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
    $('#i_dtc')
    $('.table-active').removeClass('table-active')
    $('#i_code').val('')
    $('#i_id').val('')
    $("textarea[id*='ta_']").val('')
    $("input[id*='i_']").val('')
    $("input[id*='chb_']").attr('checked', false)
    $("span[id*='s_']").html('')
    $("tbody[id*='tbody_array_']").html('')
    $('label[id*="l_file_"]').html('')
    $('div[id*="div_formula_"]').html('')
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
            fast_get_link(current_node[0])
        // Заполним собственника для массивов
        let owner = $('input[name="input_owner"]')
        if (owner.length){
            let id = $("a:contains('Собственник')")[0].id.slice(8)
            $('#i_link_' + id).val(owner[0].value)
        }
        // Поработаем с закрытыми хэндлером полями
        let is_contract = get_path_from_url() === 'contract-draft'
        oorbh(dict, false, is_contract)
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
function draft_new(is_contract=false) {
    // чистим
    $('.table-active').removeClass('table-active')
    $('#i_code').val('')
    $('#i_id').val('')
    $('#i_dtc').val('')
    let headers = $('span[id^="header_info"]')
    // включим доступность данных, запрещенных из-за включенного делея и хэндлера
    for (let i = 0; i < headers.length; i++){
        let json_obj = JSON.parse(headers[i].innerText)
        if (is_contract && json_obj.delay.delay && json_obj.delay.handler || !is_contract && json_obj.delay
            && json_obj.delay_settings.handler)
            oorbh(json_obj, false, is_contract)
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


// pdl = promp draft link
function pdl(this_input, class_id, is_contract) {
    clearTimeout(timer_link)
    timer_link = setTimeout(()=>{
        let id = this_input.id.slice(7)
        let result = $('#s_link_' + id)
        $.ajax({url:'draft-link',
                method:'get',
                dataType:'json',
                data: {class_id: class_id, is_contract: is_contract, value: this_input.value},
                success:function(data){
                    if ('error' in data)
                        result.text(data.error)
                    else{
                        result.text('')
                        let dl = $('#dl_' + id)
                        dl.html('')
                        for (let i = 0; i < data.length; i++){
                            let op = document.createElement('option')
                            op.value = data[i].id
                            op.innerText = data[i].data
                            dl.append(op)
                        }
                        if (data.length === 1 && Boolean(parseInt(this_input.value))){
                            let url = (is_contract) ? 'contract-draft' : 'table-draft'
                            url += '?class_id=' + JSON.parse($('#i_current_class').val()).parent
                            let link_text = '<a target="_blank" href="' + url + '&draft_id=' + data[0].id + '">от '
                                + data[0].timestamp + '</a>'
                            result.html(link_text)
                        }
                    }
                },
                error: function () {
                    result.text('Ошибка')
                }
            })
    }, 1000)
}


function pack_search(){

}


function fill_tps(object){
    if (!tps)
        tps = JSON.parse($('#tps').html())
        json_object['new_tps'] = []
    for (let k in object){
        if (typeof object[k] === 'object'){
            for (let kk in object[k]){
                if (kk.match(/tp_/)){
                    let tp_id = parseInt(kk.slice(5))
                    let tp = tps.find(el => el.id === tp_id)
                    let dict_tp = {'id': tp_id, 'control_field': tp.cf, 'stages': []}
                    for (let i =0; i < tp.stages.length; i++){
                        let stage = {'id': tp.stages[i].id}
                        stage.value = {'fact': object[k][kk][tp.stages[i].id], 'delay': []}
                        dict_tp.stages.push(stage)
                    }
                    json_object.new_tps.push(dict_tp)
                }
            }
        }
    }
}


function change_cf(this_input){
    clearTimeout(timer_link)
    timer_link = setTimeout(() =>{
        let cf_id = parseInt(this_input.id.slice(8))
        let new_val = (this_input.value) ? parseFloat(this_input.value) : 0
        let my_tps = tps.filter(el => el.cf === cf_id)
        let old_val = 0
        for (let i = 0; i < my_tps[0].stages.length; i++){
            let stage = $('#i_stage_' + my_tps[0].stages[i].id)
            if (stage.val())
                old_val += parseFloat(stage.val())
        }
        let delta = new_val - old_val
        for (let i = 0; i < my_tps.length; i++){
            let new_first_stage = $('#i_stage_' + my_tps[i].stages[0].id)
            let old_val_first_stage = (new_first_stage.val()) ? parseFloat(new_first_stage.val()) : 0
            new_first_stage.val(old_val_first_stage + delta)
        }
    }, 500)
}