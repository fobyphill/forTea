// Переменные для таймера запуска аякса
var typingTimer;
var doneTypingInterval = 1000;
var json_object = {}
var array_delay = []
var timeline_delay = []
var form_control_init = false
var arrays = JSON.parse($('#s_arrays').html())

// Страница управления всеми типами объектов - справочниками, контрактами, словарями, массивами
function escapeHtml(unsafe) {
    return $('<div />').text(unsafe).html()
}

function unescapeHtml(safe) {
    return $('<div />').html(safe).text();
}

// процедура заполнения данных формы выделенного объекта
function fill_object_form(is_contract=false, is_draft=false) {
    if (is_draft)
        $('#i_id').val(json_object.id)
    let headers = $("span[id*='header_info']")
    // Вкинем данные в поля формы редактирования класса
    if (json_object.type === 'dict'){
        let owner =$('#i_owner')
        owner.val(json_object.code)
        ajax_link_def($('#parent_id').val(), owner.val(), $('#parent_type').val(), $('#s_owner')[0])
        $('#b_save_dict').attr('onclick', 'pack_search(); send_form_with_param("b_save")')
    }
    else $('#i_code').val(json_object.code)
    // обернем в ссылку код
    let location = (is_contract) ? 'contract' : 'table'
    let url = 'hist-reg?i_date_in=1970-01-01T00:00&i_filter_object=' + json_object.code + '&i_filter_class='
        + json_object.parent_structure + '&s_type=' + json_object.type + '&s_location=' + location
    $('#a_code').attr('href', url)
    let branch_val = null
    let select_dicts = $('#new_dict')
    select_dicts.html('')
    let div_wrapper_dicts = $('#div_wrapper_dicts')
    div_wrapper_dicts.html('')
    for (let k in json_object){
        // Заполним собственника, если он есть
        if (k === 'parent_code'){
            let owner = $('#i_owner')
            owner.val(json_object.parent_code)
            ajax_link_def($('#parent_id').val(), owner.val(), $('#parent_type').val(), $('#s_owner')[0])
        }
        // Заполним ветку (если она есть)
        if (typeof json_object[k] === 'object' && json_object[k] && Object.keys(json_object[k]).includes('name')
            && json_object[k].name === 'parent_branch'){
            branch_val = json_object[k].value
            break
        }
        else if (k === 'branch')
            branch_val = json_object[k]

        // заполним массивы, если они есть
        else if (typeof json_object[k] === 'object' && json_object[k] && Object.keys(json_object[k]).includes('headers')){
            fill_arrays(json_object[k].objects, k, is_draft)
        }
        // заполним новые техпроцессы
        else if (k === 'new_tps'){
            // Обнулим ТПСы
            $('input[id*="i_stage_"]').val('')
            $('span[id*="s_stage_"]').text('')
            let tps = JSON.parse($('#tps').text())
            for (let i = 0; i < tps.length; i++){
                let current_tp = json_object.new_tps[i]
                let cf_val = (current_tp.control_field in json_object && json_object[current_tp.control_field].value) ?
                    json_object[current_tp.control_field].value : 0
                let stage_0 = tps[i].stages[0]
                let vals = $('#i_stage_' + stage_0.id + '')
                vals.val(cf_val)
                let fact_dels = $('#s_stage_' + stage_0.id + '_fact')
                fact_dels.text(cf_val)
            }
            // Если данные прибыли - работаем с ними
            let data = json_object[k]
            if (data.length){
                for (let i = 0; i < data.length; i++){
                    for (let j = 0; j < data[i].stages.length; j++){
                        let stage_data = data[i].stages[j].value
                        if (stage_data){
                            let fact = stage_data.fact
                            if (!fact) fact = 0
                            let delay = stage_data.delay
                            if (!delay) delay = 0
                            else {
                                let sum = 0
                                for (let k = 0; k < delay.length; k++){
                                    sum += delay[k].value
                                }
                                delay = sum
                            }
                            let stage = delay + fact
                            $('#i_stage_' + data[i].stages[j].id).val((stage) ? stage : '')
                            $('#s_stage_' + data[i].stages[j].id + '_fact').text((fact) ? fact : '')
                            $('#s_stage_' + data[i].stages[j].id + '_delay').text((delay) ? delay : '')
                            $('#s_stage_' + data[i].stages[j].id + '_start_delay').text((delay) ? delay : '')
                        }
                    }
                }
            }
        }
        // заполним словари
        else if (k.slice(0, 4) === 'dict'){
            let dict_id = k.slice(5)
            let header_dict = JSON.parse($('#header_dict' + dict_id).html())
            if (json_object[k]){
                let wrapper_local = document.createElement('div')
                wrapper_local.className = 'input-group mb-3'
                div_wrapper_dicts.append(wrapper_local)
                let span_dict = document.createElement('span')
                span_dict.className = 'input-group-text'
                wrapper_local.appendChild(span_dict)
                let a = document.createElement('a')
                a.target = '_blank'
                a.innerText = header_dict.name
                a.href = 'hist-reg?i_date_in=1970-01-01T00:00&i_filter_class=' + dict_id + '&i_filter_object=' +
                json_object[k].code + '&s_type=dict'
                span_dict.appendChild(a)
                let div_dict = document.createElement('div')
                div_dict.className = 'form-control'
                div_dict.style = 'display: initial; width: initial; height: initial; padding: 0; border: 0'
                div_dict.id = 'div_dict' + dict_id
                wrapper_local.appendChild(div_dict)
                fill_dict(json_object[k], header_dict, div_dict)
            }
            else {
                let opt = document.createElement('option')
                opt.value = dict_id
                opt.innerText = header_dict.name
                select_dicts.append(opt)
            }
            update_dict(header_dict.id)
        }
    }
    if (branch_val)
        $('#i_branch').val(branch_val)
    else $('#i_branch').val('')

    if (!select_dicts.children().length)
        $('#div_footer_dict').attr('class', 'tag-invis')
    else $('#div_footer_dict').attr('class', 'input-group mb-3')

    // Зачистим делэи
    $('input[id$="_delay_datetime"]').val('')
    $('input[id$="_delay"]').val('').attr('checked', false)
    $('textarea[id$="_delay"]').val('')
    $('select[id$="_delay"]').val('')
    $('input[id^="chb_"]').val('True')

    for (let i = 0; i < headers.length; i++) {
        let header = JSON.parse(headers[i].innerText)
        let is_delay
        if (is_contract)
            is_delay = (header.delay) ? header.delay.delay : false
        else if  (json_object.type === 'table' || json_object.type === 'array')
            is_delay = header.delay
        if (is_draft)
            is_delay = false
        let delay = ''
        let handler
        if (is_delay){
            if (is_contract)
                handler = (header.delay) ? header.delay.handler : null
            else handler = header.delay_settings.handler
            // добавим state и делэй для чисел
            if (header.formula === 'float'){
                if (header.id in json_object){
                    let val = (json_object[header.id].value) ? json_object[header.id].value : 0
                    let delays = json_object[header.id].delay
                        let delay = 0
                        if (Boolean(delays && delays.length)){
                            for (let j = 0; j < delays.length; j++)
                                delay += delays[j].value
                        }
                        val += delay
                    $('#s_' + header.id + '_state').text(val)
                    $('#i_float_' + header.id + '_sum_delay').val((delay !== 0) ? delay : '')
                }
                else $('#s_' + header.id + '_state').text('')
            }
            // добавим делэй для остальных типов данных
            else{
                if (header.id in json_object){
                    if ('delay' in json_object[header.id] && json_object[header.id].delay && json_object[header.id].delay.length){
                        let all_delays = json_object[header.id].delay
                        delay = {'date_update':'3333-12-31'}
                        for (let i = 0; i < all_delays.length; i++){
                            if (all_delays[i].date_update < delay.date_update)
                                delay = all_delays[i]
                        }
                        delay = delay.value
                    }
                }
            }
        }
        // обернем в ссылку описание параметра
        if (json_object[header.id]){
            let is_link = true
            if (Object.keys(json_object[header.id]).includes('type')){
                if (json_object[header.id].type === 'eval')
                    is_link = false
            }
            else if (Object.keys(json_object[header.id]).includes('headers'))
                is_link = false
            if (is_link){
                let url = 'hist-reg?i_date_in=1970-01-01T00:00&i_filter_object=' + json_object.code + '&i_name='
                    + header.id + '&i_filter_class=' + json_object.parent_structure + '&s_type=' + json_object.type
                    + '&s_location=' + location
                $('#a_label_' + header.id).attr('href', url)
            }
            else $('#a_label_' + header.id).attr('href', '')
        }
        // Добавим системные параметры контракта
        if (header.name === 'system_data'){
            $('#i_dtc').val(json_object[header.id].value.datetime_create)
            $('#chb_cc').attr('checked', json_object[header.id].value.is_done)
            let b_delete_class = (json_object[header.id].value.is_done) ? 'btn btn-danger' : 'tag-invis'
            $('#b_delete_object').attr('class', b_delete_class)
        }
        // Добавим чекбоксы
        else if (header.formula === 'bool'){
            let val = false
            if (header.id in json_object){
                val = (json_object.type === 'dict') ? (json_object[header.id].value.toLowerCase() === 'true') :
                    json_object[header.id].value
            }
            $('#chb_' + header.id).prop('checked', val)
            if (is_delay && delay)
                $('#chb_' + header.id + '_delay').prop('checked', true)
            else $('#chb_' + header.id + '_delay').prop('checked', false)

        }
        // добавим ссылки
        else if (header.formula === 'link'){
            let i_link = $('#i_link_' + header.id)
            if (i_link.length){
                let link_code = (header.id in json_object) ? json_object[header.id].value : ''
                i_link.val(link_code)
                if (link_code){
                    let class_type = (json_object.type === 'dict') ? 'd': location[0]
                    if (is_draft && header.name === 'Собственник' && json_object.type === 'array')
                        pdl(i_link[0], json_object.parent_structure, is_contract)
                    else
                        fast_get_link(i_link[0], class_type)
                }
                else {
                    i_link.val('')
                    $('#s_link_' + header.id).html('')
                    if (is_draft && header.name === 'Собственник' && json_object.type === 'array')
                        pdl(i_link[0], json_object.parent_structure, is_contract)
                    else
                        promp_link(i_link[0], is_contract)
                }
                if (is_delay){
                    let link_delay = $('#i_link_' + header.id + '_delay')
                    link_delay.val(delay)
                    promp_link(link_delay[0], is_contract)
                    let class_type = (json_object.type === 'dict') ? 'd': location[0]
                    fast_get_link(link_delay[0], class_type)
                }
            }
            // для родителя дерева
            else if(header.name === 'parent'){
                $('#i_parent').val(json_object[header.id].value)
            }
        }
        // добавим датавремя
        else if (header.formula === 'datetime'){
            let date_time = (header.id in json_object) ? json_object[header.id].value : ''
            if (date_time)
                $('#i_datetime_' + header.id).val(date_time)
            else
                $('#i_datetime_' + header.id).val('')
            if (is_delay)
                $('#i_datetime_' + header.id + '_delay').val(delay)
        }
        // добавим дату
        else if (header.formula === 'date'){
            if (header.id in json_object)
                $('#i_date_' + header.id).val(json_object[header.id].value)
            else $('#i_date_' + header.id).val('')
            if (is_delay)
                $('#i_date_' + header.id + '_delay').val(delay)
        }
        // Добавим числа
        else if (header.formula === 'float'){
            let val = (header.id in json_object) ? json_object[header.id].value : ''
            if (val)
                val = (parseFloat(val) !== parseInt(val)) ? parseFloat(val).toFixed(2) : parseInt(val)
            $('#i_float_' + header.id).val(val)
        }
        // Добавим перечисления
        else if (header.formula === 'enum'){
            let tag_enum = $('#s_enum_' + header.id)[0]
            let val = (header.id in json_object) ? json_object[header.id].value : null
            let is_find = false
            for (let j = 0; j < tag_enum.children.length; j++){
                if (tag_enum.children[j].value === val){
                    tag_enum.selectedIndex = j
                    is_find = true
                    break
                }
            }
            if (!is_find)
                tag_enum.selectedIndex = 0
            if (is_delay){
                let tag_enum_delay = $('#s_enum_' + header.id + '_delay')[0]
                tag_enum_delay.selectedIndex = 0
                if (delay){
                    for (let j = 0; j < tag_enum_delay.children.length; j++){
                        if (tag_enum_delay.children[j].value === delay){
                            tag_enum_delay.selectedIndex = j
                            break
                        }
                    }
                }
            }
        }
        // Добавим алиасы
        else if (header.formula === 'const'){
            // Заполним select
            let select_alias = $('#s_alias_' + header.id)
            let alias_opts = select_alias.children()
            alias_opts.attr('selected', false)
            let alias_val = (header.id in json_object) ? json_object[header.id].value : null
            for (let j = 0; j < alias_opts.length; j++){
                if (alias_val === parseInt(alias_opts[j].value)){
                    alias_opts[j].setAttribute('selected', true)
                    break
                }
            }
            recount_alias(select_alias[0])  // заполним результат константы
            $('#div_alias_' + header.id + '_delay').html('')
            if (is_delay && delay){
                let select_delay = $('#s_alias_' + header.id + '_delay')
                let alias_opts = select_delay.children()
                alias_opts.attr('selected', false)
                for (let j = 0; j < alias_opts.length; j++){
                    if (delay === parseInt(alias_opts[j].value)){
                        alias_opts[j].setAttribute('selected', true)
                        break
                    }
                }
            recount_alias(select_delay[0])  // заполним результат константы
            }
        }
        // добавим файл
        else if(header.formula === 'file'){
            $('#i_file_' + header.id).val('')
            let hist_range = $('#i_hist_range')[0]
            let label = $('#l_file_'+ header.id)
            let b_del_file = $('#b_del_file_' + header.id)
            let b_save_file = $('#b_save_file_' + header.id)
            let b_show_file = $('#b_show_file_' + header.id)
            let filename = $('#i_filename_' + header.id)
            if (header.id in json_object){
                let file_name = json_object[header.id].value
                if (file_name){
                    label.html(file_name.slice(14))
                    b_save_file.attr('class', 'btn btn-outline-primary')
                    b_show_file.attr('class', 'btn btn-outline-primary')
                    if ((!hist_range || parseInt(hist_range.value) >= parseInt(hist_range.max)) && !handler)
                        b_del_file.attr('class', 'btn btn-outline-danger')
                    else b_del_file.attr('class', 'tag-invis')
                    filename.val(file_name)
                    let full_file_name = (is_draft) ? 'd' : 'h'
                    full_file_name += file_name
                    $('#s_filename_' + header.id).html(full_file_name)
                }
                else {
                    label.html('Выберите файл')
                    b_del_file.attr('class', 'tag-invis')
                    b_save_file.attr('class', 'tag-invis')
                    b_show_file.attr('class', 'tag-invis')
                    filename.val('')
                    $('#s_filename_' + header.id).html('')
                }
                filename.val(file_name)
            }
            else {
                label.html('Выберите файл')
                filename.val('')
                b_del_file.attr('class', 'tag-invis')
                b_save_file.attr('class', 'tag-invis')
                b_show_file.attr('class', 'tag-invis')
                $('#s_filename_' + header.id).html('')
            }
            label[0].parentElement.style.height = String(label[0].clientHeight) + 'px'
            // заполним делэйные значения
            if (is_delay){
                $('#i_file_' + header.id + '_delay').val('')
                let label_delay = $('#l_file_'+ header.id + '_delay')
                let b_save_file_delay = $('#b_save_file_' + header.id + '_delay')
                let b_show_file_delay = $('#b_show_file_' + header.id + '_delay')
                let filename_delay = $('#i_filename_' + header.id + '_delay')
                if (delay){
                    delay = delay.slice(14)
                    label_delay.html(delay)
                    b_save_file_delay.attr('class', 'btn btn-outline-primary')
                    b_show_file_delay.attr('class', 'btn btn-outline-primary')
                    filename_delay.val(delay)
                    let full_file_name = (is_draft) ? 'd' : 'h'
                    full_file_name += delay
                    $('#s_filename_' + header.id + '_delay').html(full_file_name)
                }
                else{
                    label_delay.html('Выберите файл')
                    b_save_file_delay.attr('class', 'tag-invis')
                    b_show_file_delay.attr('class', 'tag-invis')
                    filename_delay.val('')
                    $('#s_filename_' + header.id + '_delay').html('')
                }
                label_delay[0].parentElement.style.height = String(label[0].clientHeight) + 'px'
            }
        }
        // добавим формулы
        else if (header.formula === 'eval'){
            let val = (header.id in json_object) ? json_object[header.id].value : ''
            if (typeof val === 'object')
                val = JSON.stringify(val)
            else if (typeof val == 'boolean')
                val = String(val)
            $('#div_formula_' + header.id).html(val).attr('style', 'height: auto')
        }
        else{
            let string_tag = $('#ta_' + header.id)
            if (string_tag.length){
                string_tag.val((header.id in json_object) ? json_object[header.id].value : null)
                if (is_delay)
                    $('#ta_' + header.id + '_delay').val(delay)
            }
            else{
                // для заголовков веток деревьев
                $('#i_name').val((header.id in json_object) ? json_object[header.id].value : null)
            }
        }
    }
    // добавим ссылки на массивы
    let my_path
    if (is_draft)
        my_path = (is_contract) ? '/contract-draft' : '/table-draft'
    else my_path = (is_contract) ? '/contract' : '/manage-object'

    for (let i = 0; i < arrays.length; i++){
        if (is_draft){
            let iframe_url = my_path + '?class_id=' + arrays[i].id + '&input_owner=' + json_object.code
            $('#iframe_' + arrays[i].id).attr('src', new_link_url)
        }
        else{
            let link_array = $('#a_array_' + arrays[i].id)
            let new_link_text = link_array.attr('href').replace(/input_owner=.*$/, 'input_owner=' + json_object.code)
            link_array.attr('href', new_link_text)
            let iframe_url = my_path + '?class_id=' + arrays[i].id + '&input_owner=' + json_object.code
            $('#iframe_' + arrays[i].id).attr('src', iframe_url)
        }
    }
    if ((!form_control_init || is_draft) && json_object.type !== 'tree'){
        form_control_init = true
        let not_draft_new = (is_draft) ? Boolean(json_object.code) : true
        for (let i = 0; i < headers.length; i++){
            let header = JSON.parse(headers[i].innerText)
            let handler
            if (is_contract)
                handler = (header.delay) ? header.delay.handler : null
            else if (json_object.type === 'table')
                handler = header.delay_settings.handler
            let is_delay
            if (is_contract){
                is_delay = (header.delay) ? header.delay.delay : false
            }
            else is_delay = header.delay
            let readonly = is_delay && Boolean(handler) && not_draft_new
            oorbh(header, readonly, is_contract)
        }
    }
}

// Заполнить словари на странице объектов
function fill_dicts(json_object){
    let div_wrapper_dicts = $('#div_wrapper_dicts')[0]
    if (div_wrapper_dicts){
       div_wrapper_dicts.innerHTML = ''
        let select = $('#new_dict')[0]
        select.innerHTML = ''
        for (let k in json_object){
            if (k.slice(0, 4) === 'dict'){
                let dict_id = k.slice(5)
                let header_dict = JSON.parse($('#header_dict' + dict_id).html())
                if (json_object[k] && Object.keys(json_object[k]).length){
                    let wrapper_local = document.createElement('div')
                    wrapper_local.className = 'input-group mb-3'
                    div_wrapper_dicts.appendChild(wrapper_local)
                    let span_dict = document.createElement('span')
                    span_dict.className = 'input-group-text'
                    wrapper_local.appendChild(span_dict)
                    let a = document.createElement('a')
                    a.target = '_blank'
                    a.innerText = header_dict.name
                    a.href = 'hist-reg?i_date_in=1970-01-01T00:00&i_filter_class=' + dict_id + '&i_filter_object=' +
                    json_object[k].code + '&s_type=dict'
                    span_dict.appendChild(a)
                    let div_dict = document.createElement('div')
                    div_dict.className = 'form-control'
                    div_dict.style = 'display: initial; width: initial; height: initial; padding: 0; border: 0'
                    div_dict.id = 'div_dict' + dict_id
                    wrapper_local.appendChild(div_dict)
                    fill_dict(json_object[k], header_dict, div_dict)
                }
                else {
                    let opt = document.createElement('option')
                    opt.value = dict_id
                    opt.innerText = header_dict.name
                    select.appendChild(opt)
                }
                update_dict(header_dict.id)
            }
        }
        if (!select.children.length)
            $('#div_footer_dict').attr('class', 'tag-invis')
        else $('#div_footer_dict').attr('class', 'input-group mb-3')
    }
}

function change_file_label(input){
    let id = input.id.slice(7)
    let label = $('#l_file_' + id)[0]
    let input_name = $('#i_filename_' + id)
    if (input.value){
        label.innerText = input.value.match(/\\([^\\]+)$/)[1]
        input_name.val(label.innerText)
        // input_name.attr('name', 'i_filename_' + id)
    }
    else label.innerText = 'Выберите файл'
    input.parentElement.style.height = String(label.clientHeight) + 'px'
}

// Вызов универсального модального окна
function open_modal_with_params(param, val=false) {
    let button_do_name = $('#button_do_name')
    switch (param){
        case 'b_del_file':
            $('#span_header').html('Удаление файла')
            $('#div_body_text').html('Вы пытаетесь удалить файл. Восстановление невозможно. Подтвердите намерение')
            button_do_name.html('Удалить')
            break
        case  'b_del_draft':
            $('#span_header').html('Удаление черновика')
            $('#div_body_text').html('Вы пытаетесь удалить черновик. Действие необратимо. Подтвердите намерение')
            button_do_name.html('Удалить')
            break
    }
    let function_full_name = 'send_form_with_param("' + param + '", ' + val + ')'
    button_do_name.attr('onclick', function_full_name)
    $('#universal_modal').modal('show');
}

// Подсказка "собственник" для словарей
function promp_owner(this_input) {
    clearTimeout(typingTimer);
    typingTimer = setTimeout(() =>{
        let class_id = get_param_from_url('class_id')
        let link = this_input.value
        let result = $('#dl_owner')[0]
        $.ajax({url:'promp-owner',
            method:'get',
            dataType:'json',
            data: {link: link, class_id: class_id},
            success:function(data){
                result.innerText = ''
                data.forEach((d) =>{
                    let op = document.createElement('option')
                    op.value = d.code
                    op.innerText = d.value
                    result.appendChild(op)
                })
            },
            error: function () {
                result.innerText = ''
            }
        })
    }, doneTypingInterval)
}

// Двигаем ползунок  location = t, c, d
function moove_time() {
    let path = get_path_from_url()
    let location = (path === 'tree') ? $('#div_location').text() : (path[0] === 'm') ? 't' : path[0]
    let code, class_id
    if (Object.keys(json_object).length){
        class_id = json_object.parent_structure
        code = json_object.code
    }
    else{
        class_id = get_param_from_url('class_id')
        code = $('tr.table-active')[0].id
        if (code[0] === 'u')
            code = code.slice(4)
    }
    let event_name = $('#s_hist_range')
    event_name.text('Информация загружается')
    let [timestamp, event_num] = get_timestamp()
    if (timestamp !== 'now'){
        $.ajax({url: 'get-object-version',
        method:'get',
        dataType:'json',
        data: {class_id: class_id, code: code, location: location, timestamp: timestamp},
        success:function(data){
            if ('error' in data)
                $('#div_msg').html('Ошибка. ' + data.error).addClass('text-red')
            else{
                $('#div_msg').html('').removeClass('text-red')
                if (Object.keys(json_object) && json_object.type === 'contract'){
                    if ('completion_condition' in json_object){
                        let cc = json_object.completion_condition
                        json_object = data
                        json_object.completion_condition = cc
                    }
                    else {
                        json_object = data
                        do_cc(json_object)
                    }
                }
                else json_object = data
                fill_object_form((location === 'c'))
                // Если мы находимся внутри истории, закроем для редактирование таймлайн планирования, выключим сохранение
                $('#b_save').prop('disabled', true)
                let tl_delay = $('#div_tl_delay')
                if (tl_delay.attr('class') !== 'tag-invis')
                    tl_delay.attr('class', 'div-disabled')
                if (array_timeline.timeline.length)
                    event_name.text(date_time_to_rus(array_timeline.timeline[event_num].date_update) + ' '
                        + array_timeline.timeline[event_num].user)
                else event_name.text(date_time_to_rus(timestamp))
            }
        },
        error: function (data) {
            $('#s_object_hist').html('error')
            $('#s_hist_range').html('Ошибка')
            $('#div_msg').text('Ошибка: ' + data.responseText).attr('class', 'text-red')
        }
    })
    }
    else{
        $('#b_save').prop('disabled', false)
        get_full_object(json_object.parent_structure, json_object.code, location)
        event_name.text(date_time_to_rus(array_timeline.timeline[event_num].date_update) + ' '
                    + array_timeline.timeline[event_num].user)
    }
}

// двигаем ползунок будущего
function moove_delay(){
    let event_num = parseInt($('#i_delay_range').val())
    let current_version = array_delay[event_num]
    if (event_num)
        $('#div_tl_hist').attr('class', 'div-disabled')
    else
        $('#div_tl_hist').removeClass('div-disabled')

    let version_date = (event_num === 0) ? 'Сейчас' : date_time_to_rus(timeline_delay[event_num - 1])
    $('#s_delay_range').text(version_date)
    let b_save = $('#b_save')
    if (event_num)
        b_save.attr('disabled', true)
    else b_save.attr('disabled', false)

    let is_contract = (get_path_from_url()[0] === 'c')
    json_object = current_version
    fill_object_form(is_contract)
}

// Красиво выводим дату-время
function date_time_to_rus(date_time) {
    if (date_time){
        date_time =  date_time.slice(8, 10) + '.' + date_time.slice(5, 7) + '.' + date_time.slice(0, 4) + ' ' +
        date_time.slice(11, 19) + ' ' + date_time.slice(27)
    }
    else date_time = ''
    return date_time
}

function date_to_rus(date) {
    return (date) ? date.slice(8, 10) + '.' + date.slice(5, 7) + '.' + date.slice(0, 4) : ''
}

// Показать расположение файла
function show_file_location(header_id, is_contract=false) {
    let full_name = $('#s_filename_' + header_id).html()
    if (full_name){
        let filename = full_name.slice(1,)
        let class_id = get_param_from_url('class_id')
        let root_folder = (full_name[0] === 'h') ? 'database_files_history/' : 'database_files_draft/'
        let path = (is_contract) ? 'contract_' : 'table_'
        path += class_id
        path = root_folder + path
        let date_folder = filename.slice(4, 8) + '-' + filename.slice(2, 4) + '-' + filename.slice(0, 2)
        let result = path + '/' + date_folder + '/' + filename
        copyToClipboard(result)
        result += '\nскопировано в буфер обмена'
        alert(result)
    }
}

function copyToClipboard(text) {
    if (window.clipboardData && window.clipboardData.setData) {
        // Internet Explorer-specific code path to prevent textarea being shown while dialog is visible.
        return window.clipboardData.setData("Text", text);
    }
    else if (document.queryCommandSupported && document.queryCommandSupported("copy")) {
        var textarea = document.createElement("textarea");
        textarea.textContent = text;
        textarea.style.position = "fixed";  // Prevent scrolling to bottom of page in Microsoft Edge.
        document.body.appendChild(textarea);
        textarea.select();
        try {
            return document.execCommand("copy");  // Security exception may be thrown by some browsers.
        }
        catch (ex) {
            console.warn("Copy to clipboard failed.", ex);
            return prompt("Copy to clipboard: Ctrl+C, Enter", text);
        }
        finally {
            document.body.removeChild(textarea);
        }
    }
}

function select_branch(this_li) {
    $('.table-active').removeClass('table-active')
    this_li.className = 'row table-active'
    let code = this_li.id.slice(4)
    let page = $('input[name="page"]')
    if (page.length)
        page[0].value = '1'
    let params = {'branch_code': code, 'date_from': $('#i_timeline_from').val(), 'date_to': $('#i_timeline_to').val()}
    send_form_with_params(params)
}

function edit_branch(e){
    e.stopPropagation()
    send_form_with_param('edit_branch', this.parentNode.id.slice(4))
}

// выбор черновика
function select_draft(this_select, is_contract=false) {
    let draft_id = this_select.value
    if (draft_id !== '0'){
        let all_drafts = JSON.parse($('#s_drafts').html())
        let my_draft = all_drafts.find(d=>{ return String(d.id) === draft_id})
        fill_object_form(my_draft.data, is_contract, true)
        fill_dicts(my_draft.data)
        $('#s_hist_range').html('Черновик')
        $('#i_hist_range').attr('disabled', true)
    }
    else{
        let current_version = JSON.parse($('#s_current_version').html())
        fill_object_form(current_version, is_contract, false)
        let i_hist_range = $('#i_hist_range')
        i_hist_range.attr('disabled', false).val(i_hist_range.attr('max'))
        moove_time()
    }

}

function fill_arrays(objects, array_id, is_draft=false){
    let table_array = $('#table_array_' + array_id)
    if (objects.length)
        table_array.removeClass('tag_invis')
    else table_array.addClass('tag_invis')
    let tbody = $('#tbody_array_' + array_id)
    tbody.html('')
    for (let j = 0; j < objects.length; j++){
        if ('is_active' in objects[j] && !objects[j].is_active)
            continue
        let tr = document.createElement('tr')
        tr.className = 'row'
        tr.id='trar_' + array_id + '_' + objects[j].code
        tr.setAttribute('style', 'margin: 0;')
        tbody.append(tr)
        // Пройдем по полям, создадим столбцы
        // Столбец №
        let td_num = document.createElement('td')
        td_num.className = 'col-1 text-right'
        td_num.setAttribute('style', 'padding: 0')
        td_num.innerText = j + 1
        tr.appendChild(td_num)
        let headers_tags = $('th[id^="td_header_' + array_id + '"]')
        let re = /^td_header_\d+\|(\d+)/
        for (let k = 0; k < headers_tags.length; k++){
            let header_id = headers_tags[k].id.match(re)[1]
            let td = document.createElement('td')
            td.className = 'col text-center'
            td.setAttribute('style', 'padding: 0')
            for (let key in objects[j]){
                if (key === header_id){
                    let obj = objects[j][key]
                    // приведение типов
                    let val
                    if (obj.formula === 'bool')
                        val = (obj.value) ? '&#10003;' : ''
                    else if (obj.formula === 'const')
                        val = ('result' in obj) ? obj.result : obj.value
                    else if (obj.formula === 'link' && obj.data){
                        let url = (obj.data.type === 'contract') ? 'contract' : 'manage-object'
                        url += '?class_id=' + obj.data['parent_structure'] + '&object_code=' + obj.data.code
                        let main_field = (obj.data.type === 'contract') ? 'system_data' : 'Наименование'
                        let link_label = ''
                        for (let keykey in obj.data){
                            if (typeof(obj.data[keykey]) === 'object'){
                                if (obj.data[keykey].name === main_field){
                                    link_label = (obj.data.type === 'contract') ? obj.data[keykey].value.datetime_create : obj.data[keykey].value
                                    break
                                }
                            }
                        }
                        if (obj.data.type === 'contract')
                            link_label = date_time_to_rus(link_label)
                        val = '<a href="' + url + '" target="_blank">' + link_label + '</a>'
                    }
                    else if (obj.formula === 'datetime')
                        val = (obj.value) ? date_time_to_rus(obj.value) : ''
                    else if (obj.formula === 'date')
                        val = (obj.value) ? date_to_rus(obj.value) : ''
                    else if (obj.formula === 'file')
                        val = (obj.value) ? obj.value.slice(14) : ''
                    else val = obj.value
                    td.innerHTML = val
                    break
                }
            }
            tr.appendChild(td)
        }
    }

    if (is_draft){
        let obj_ids = []
        objects.forEach(o => obj_ids.push(o.id))
        $('#i_slave_' + array_id).val(JSON.stringify(obj_ids))
    }
    // Если у массива есть техпроцессы - показать их
    if (objects.length){
        let my_array = arrays.find((el) => el.id === parseInt(array_id))
        if ('tps' in my_array)
            crebushot(array_id)
    }
}

function change_timeline_interval(date_to_now=false){
    if (date_to_now)
        $('#i_timeline_to').val(new Date().toLocaleString('sv'))
    let active_row = $('.row.table-active')
    let url = get_path_from_url()
    let location = (url === 'tree') ? $('#div_location').html() : (url[0] === 'm') ? 't' : url[0]
    for (let i = 0; i < active_row.length; i++){
        if (active_row[i].id[0] !== 'u'){
            active_row[i].classList.remove('table-active')
            sao(active_row[i], location)
            break
        }
    }
}


// location = t, c, d; sao = select active object
function sao(this_object, location='t', first_click=false) {
    if (this_object.parentElement.tagName === 'THEAD' || this_object.classList.contains('table-active'))
        return false
    if (this_object.parentElement.tagName === 'TFOOT' || this_object.classList.contains('table-active'))
        return false
    if (!first_click)
        $('#div_msg').text('').removeClass('text-red')
    $('#data-table tr.table-active').each((i, el)=>{el.className = 'row'})
    $(this_object).addClass('table-active');
    let code = (this_object.id[0] === 'u') ? this_object.id.slice(4) : this_object.id
    let class_id = get_param_from_url('class_id')
    $('#div_tl_hist').removeClass('div-disabled')
    // Известим пользователя о том, что информация загружается
    $('#s_hist_range').text('Информация загружается')
    $('#i_hist_range').val('0').attr('max', '0')
    let timeline_to = $('#i_timeline_to')
    let date_to = new Date()
    // Поставим стандартный период времени - месяц
    if (!timeline_to.val())
        timeline_to.val(date_to.toLocaleString('sv'))
    let timeline_from = $('#i_timeline_from')
    if (!timeline_from.val()){
        let date_from = new Date()
        date_from.setMonth(date_to.getMonth() - 1)
        timeline_from.val(date_from.toLocaleString('sv'))
    }
    // Подготовим время для таймлайна делэя
    let tl_from_delay = $('#i_tl_delay_from')
    let tl_to_delay = $('#i_tl_delay_to')
    if (!tl_from_delay.val())
        tl_from_delay.val(date_to.toLocaleString('sv'))
    if (!tl_to_delay.val()){
        let delay_date_to = new Date(date_to.setMonth(date_to.getMonth() + 1))
        tl_to_delay.val(delay_date_to.toLocaleString('sv'))
    }
    json_object = {}
    $('input[id^="i_stage_"]').attr('readonly', false)
    roh(class_id, code, location)
    $('#span_br').removeClass('text-red')
    $('#chb_br').prop('checked', true)
}

function go_timeline_page(page_num) {
    $('#s_tl_page_num').text(page_num)
    let page_quantity = Math.ceil(array_timeline.timeline.length / 10)
    let b_next = $('#b_tl_next')
    b_next.attr('onclick', 'go_timeline_page(' + String(page_num - 1) + ')')
    let b_prev = $('#b_tl_prev')
    b_prev.attr('onclick', 'go_timeline_page(' + String(page_num + 1) + ')')
    let hist_range = $('#i_hist_range')
    let rec_on_page = (page_num === page_quantity) ? array_timeline.timeline.length % 10 : 10
    if (hist_range.attr('max') !== rec_on_page - 1){
        hist_range.attr('max', rec_on_page - 1)
        let steplist = $('#steplist')
        steplist.html('')
        for (let i = 1; i < rec_on_page; i++){
            let op = document.createElement('option')
            op.innerText = i
            steplist.append(op)
        }
    }
    hist_range.val(rec_on_page - 1)
    if (page_num === page_quantity){
        $('#b_tl_begin').attr('class', 'tag-invis')
        b_prev.attr('class', 'tag-invis')
        $('#b_tl_end').attr('class', 'like-a')
        b_next.attr('class', 'like-a')
    }
    else if (page_num === 1){
        $('#b_tl_begin').attr('class', 'like-a')
        b_prev.attr('class', 'like-a')
        $('#b_tl_end').attr('class', 'tag-invis')
        b_next.attr('class', 'tag-invis')
    }
    else{
        $('#b_tl_begin').attr('class', 'like-a')
        b_prev.attr('class', 'like-a')
        $('#b_tl_end').attr('class', 'like-a')
        b_next.attr('class', 'like-a')
    }
    moove_time()
}

function set_array_delay(json_object){
    timeline_delay = []
    array_delay = []
    let date_from = $('#i_tl_delay_from').val()
    let date_to = $('#i_tl_delay_to').val()
    if (date_to < date_from){
        let tmp_dt = date_from
        date_from = date_to
        date_to = tmp_dt
    }

    // Соберем массив массив структуры {дата, хедер}
    let dates_headers = {}
    for (let jo in json_object){
        if (parseInt(jo) && 'delay' in json_object[jo] && json_object[jo].delay && json_object[jo].delay.length){
            let delays = json_object[jo].delay
            for (let i = 0; i < delays.length; i++){
                if (delays[i].date_update < date_to){
                    if (delays[i].date_update in dates_headers)
                        dates_headers[delays[i].date_update].push(jo)
                    else {
                        dates_headers[delays[i].date_update] = [jo]
                        timeline_delay.push(delays[i].date_update)
                    }
                }
            }
        }
    }
    // соберем массив планирований
    timeline_delay.sort()
    for (let i = 0; i < timeline_delay.length; i++){
        let joc = (array_delay.length) ? structuredClone(array_delay[array_delay.length - 1]) : structuredClone(json_object)
        let headers = dates_headers[timeline_delay[i]]
        for (let j = 0; j < headers.length; j++){
            let new_delay = []
            let delays = joc[headers[j]].delay
            for (let k = 0; k < delays.length; k++){
                if (delays[k].date_update === timeline_delay[i]){
                    if (joc[headers[j]].formula === 'float')
                        joc[headers[j]].value += delays[k].value
                    else joc[headers[j]].value = delays[k].value
                }
                else new_delay.push(delays[k])
            }
            joc[headers[j]].delay = new_delay
        }
        array_delay.push(joc)
    }
    let steplist_delay = $('#steplist_delay')
    steplist_delay.html('')
    if (array_delay.length){
        $('#div_tl_delay').attr('class', '')
        for (let i = 1; i < array_delay.length; i++){
            let op = document.createElement('option')
            op.value = i
            steplist_delay.append(op)
        }
        $('#i_delay_range').val(0).attr('max', array_delay.length)
        $('#s_delay_range').val('Сейчас')
        array_delay.unshift(json_object)
    }
    else $('#div_tl_delay').attr('class', 'tag-invis')
}

function change_tl_delay_interval(){
    json_object = array_delay[0]
    set_array_delay(json_object)
}

function start_popovers(){
    let str_template = '<div class="popover"><div class="arrow"></div><h5 class="popover-title text-center">Отложенные значения</h5>' +
            '<div class="popover-content">' +
                '<div class="d-flex border-bottom" >' +
                    '<div class="col-4 text-center font-weight-bold">Дата-время выполнения</div>' +
                    '<div class="col-4 text-center font-weight-bold">Значение</div>' +
                    '<div class="col-4 text-center font-weight-bold">Подтвержден</div>' +
                '</div>' +
                '<div id="div_all_delays"></div>' +
            '</div>' +
            '<div class="popover-footer"><a class="btn btn-secondary btn-sm">Закрыть</a></div>' +
        '</div>'
    let tag_popover = $('[data-toggle="popover"]')
    tag_popover.popover({
        html: true,
        template: str_template
    });

    // Закрыть подсказку
    $(document).on("click", ".popover-footer .btn" , function(){
        $(this).parents(".popover").popover('hide');
    })

    // Добаваить в подсказку информацию о делэях
    tag_popover.on('shown.bs.popover', function(){
        // Поищем информацию о делэях в джейсоне
        let header_id = this.id.slice(10)
        let delays = json_object[header_id]
        let all_delays = $('#div_all_delays')
        all_delays.html('')
        if (delays && 'delay' in delays && delays.delay && delays.delay.length){
            delays.delay.sort((a, b) => a.date_update.localeCompare(b.date_update))
            for (let i = 0; i < delays.delay.length; i++){
                let tr = document.createElement('div')
                tr.className = 'd-flex border-bottom'
                let td_date = document.createElement('div')
                td_date.className = 'col-4 text-center'
                td_date.innerText = date_time_to_rus(delays.delay[i].date_update)
                tr.appendChild(td_date)
                let td_val = document.createElement('div')
                td_val.className = 'col-4 text-center'
                let val = delays.delay[i].value
                if (typeof(delays.delay[i].value) === 'boolean')
                    val = (delays.delay[i].value) ? '✓' : ''
                else if (delays.type === 'file')
                    val = val.slice(14)
                td_val.innerText = val
                tr.appendChild(td_val)
                let td_approve = document.createElement('div')
                td_approve.className = 'col-4 text-center'
                td_approve.innerText = (delays.delay[i].approve) ? '✓' : ''
                tr.appendChild(td_approve)
                all_delays.append(tr)
            }
        }
        else all_delays.html('Нет отложенных значений').attr('class', 'text-center')
    })
}

// Получить полный объект - поля, словари, массивы, техпроцессы
function get_full_object(class_id, code, location){
    $.ajax({
        url: 'gfob',
        method: 'get',
        dataType: 'json',
        data: {class_id: class_id, code: code, location: location},
        success: function (data) {
            if ('error' in data)
                $('#div_msg').html(data.error).addClass('text-red')
            else {
                json_object = data
                // непонятно, для чего это вообще
                // // для контрактов добавим поле "Условие выполенения"
                // if (Object.keys(json_object) && json_object.type === 'contract'){
                //     if ('completion_condition' in json_object){
                //         json_object = data
                //     }
                //     else{
                //         json_object = data
                //     }
                // }
                // else {
                //     json_object = data
                // }
                fill_object_form((location === 'c'))
                set_array_delay(json_object)  // Покажем и заполним таймлайн планирования
            }
        },
        error: function (data) {
            $('#s_object_hist').html('error')
            $('#s_hist_range').html('Ошибка')
            $('#div_msg').text('Ошибка' + data).attr('class', 'text-red')
        }
    })
}


// reflofi = recount float field
function reflofi(this_input, start_recount_tps){
    clearTimeout(typingTimer)
    typingTimer = setTimeout(()=>{
        let id = parseInt(this_input.id.match(/i_float_(\d+)/)[1])
        let tag_state = $('#s_float' + id + '_state')
        let delta
        let is_delay
        if (tag_state.length){
            let old_state = (tag_state.text()) ? parseFloat(tag_state.text()) : 0
            is_delay = /i_float_\d+_delay/.test(id)
            let state = (this_input.value) ? parseFloat(this_input.value) : 0
            if (is_delay){
                let fact = $('#i_float_' + id)
                let fact_val = (fact.val()) ? parseFloat(fact.val()) : 0
                state += fact_val
            }
            else{
               let delay = $('#i_float_' + id + '_delay')
                let delay_val = (delay.val()) ? parseFloat(delay.val()) : 0
                state += delay_val
            }
            state += (json_object[id].delay) ? json_object[id].delay.reduce((acum, obj) => acum + obj.value, 0) : 0
            tag_state.text(state)
            delta = state - old_state
        }
        else if (start_recount_tps){
            is_delay = false
            let tps = json_object['new_tps']
            for (let i = 0; i < tps.length; i++){
                if (tps[i].control_field === id){
                    let old_fact = 0
                    let stages = tps[i].stages
                    for (let j = 0; j < stages.length; j++){
                        let s = $('#i_stage_' + stages[j].id)
                        if (s.val())
                            old_fact += parseFloat(s.val())
                    }
                    let new_fact = (this_input.value) ? parseFloat(this_input.value) : 0
                    delta = new_fact - old_fact
                    break
                }
            }
        }
        if (start_recount_tps)
            rfsot(id, is_delay, delta)
    },  1000)
}


// oe4no = open_edit_for_new_obj
function oe4no() {
    form_control_init = false
    $('textarea[id^="ta_"], input[id^="i_float_"], input[id^="i_link_"], input[id^="i_date_"], input[id^="i_datetime_"]').attr('readonly', false)
    $('input[id$="_sum_delay"]').attr('readonly', true)
    $('input[id^="chb_"]').attr('onclick', '')
    $('select[id^=s_enum_], select[id^=s_alias_]').attr('style', '')
    let files = $('input[id^="i_filename_"]')
    for (let i = 0; i < files.length; i++){
        if (/.+(?:\d)+/.test(files[i].id)){
            let header_id = files[i].id.slice(11)
            if (!$('#i_file_' + header_id).length)
                cfiff(header_id)
        }
    }
}


function ref_page() {
    change_timeline_interval(true);
}


// Enter в полях блока фильтров
$('input[id^="sf"]').keypress(function(e) {
    if(e.keyCode === 13){
        pack_search()
        $('#form')[0].submit()
    }
});


function del_tps(array_id){
    $('tr.tr-tps-info').remove()
    crebushot(array_id)
}


// crebushot = create button show tps
function crebushot(array_id){
    let tr = document.createElement('tr')
        tr.className = 'row'
        tr.setAttribute('style', 'margin: 0;')
        $('#tbody_array_' + array_id).append(tr)
        let td = document.createElement('td')
        td.className = 'col text-center'
        td.setAttribute('style', 'padding: 0')
        tr.appendChild(td)
        let but = document.createElement('button')
        but.id = 'b_ar_add_tps_' + array_id
        but.setAttribute('onclick', 'get_tps(this, ' + json_object.code + ')')
        but.className = 'btn btn-link btn-sm'
        but.innerText = 'Добавить информацию о техпроцессах'
        td.appendChild(but)
}


function get_timestamp(){
    let tag_page_num = $('#s_tl_page_num')
    let page_num = (tag_page_num.length) ? parseInt(tag_page_num.text()) : 1
    let event_num_page = parseInt($('#i_hist_range').val())  // Получили номер события на странице
    let first_page_event_quantity = (array_timeline.timeline.length % 10) ? array_timeline.timeline.length % 10 : 10
    let page_quantity = Math.ceil(array_timeline.timeline.length / 10)
    let real_page_num = page_quantity - page_num + 1
    let event_num = 0
    for (let i = 1; i <= real_page_num; i++){
        if (i === real_page_num)
            event_num += event_num_page
        else if (i === 1)
            event_num += first_page_event_quantity
        else event_num += 10
    }
    let timestamp
    if (array_timeline.timeline.length === 0)
        timestamp = (array_timeline.just_history) ? $('#i_timeline_from').val() : 'now'
    else timestamp = (event_num === array_timeline.timeline.length - 1 && !array_timeline.just_history) ? 'now' :
        array_timeline.timeline[event_num].date_update
    return [timestamp, event_num]
}