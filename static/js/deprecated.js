// Устаревшая функция поиска в дереве по ID
function find_in_tree() {
    function the_search(search){
        for (let i = 0; i < tree.length; i++){
            if (tree[i].id === search){
                tree[i].children[0].click()
                break
            }
        }
    }
    let tree = $('li[id*="unit"]')
    let val = $('#i_search').val()
    let search = 'unit' + val
    // Найдем объект
    the_search(search)
    // Найдем словарь
    let search_dict = 'unit_dict' + val
    the_search(search_dict)
}


function seach_del_parent_id() {
    let deleted_li = $("li:contains('ID группы:')").html()
    if (deleted_li){
        let delete_content = deleted_li.match(/(.+)ID группы/)[1]
        $("li:contains('ID группы:')").html(delete_content)
    }
}


// sechist - select child stage
function sechist(this_select) {
    if (this_select.value === '0')
        return false
    let child_id = this_select.value
    let child_name = this_select.options[this_select.selectedIndex].innerText
    let parent_table = this_select.parentElement
    this_select.remove()
    let stage_id = parent_table.id.slice(13)
    let html_str = '<div class="row"><div class="col-3 p-2 text-center">' + child_id + '</div>' +
        '<div class="col text-center p-2">' + child_name + '</div>' +
        '<div class="col-3 ">' +
        '<button class="btn btn-outline-secondary mx-4"' +
        'onclick="this.parentElement.parentElement.remove(); $(\'#b_new_child_' +
        stage_id + '\').parent().parent().attr(\'class\', \'row\')">-</button></div></div></div>'
    parent_table.innerHTML = parent_table.innerHTML + html_str
    let stages = JSON.parse($('#fields').text())
    let count_stages = (stage_id === 'new') ? stages.length : stages.length - 1
    if (parent_table.children.length !== count_stages)
        $('#b_new_child_' + stage_id).parent().parent().attr('class', 'row')
}


// Из черновиков
function fill_form(this_object){
    let json_object = JSON.parse($('#json_object' + this_object.id).text())
    // Изменяем классы строк таблицы
    $('tr').removeClass('table-active');
    $(this_object).addClass('table-active');
    // Заполним отправителя
    if (json_object.sender){
        $('#div_sender').attr('class', 'input-group mb-3')
        $('#s_sender').html(json_object.sender)
    }
    else{
        $('#div_sender').attr('class', 'tag-invis')
    }
    // Заполним данные из полей таблицы
    fill_object_form(json_object, false, true)
    // Заполним словари
    fill_dicts(json_object)
    // Вкинем данные в поля формы редактирования класса
    $('#i_id').val(json_object.id)
    $('#i_code').val(json_object.code)
}

// из черновиков
function show_recepient() {
    let current_recepient = $('#i_recepient')
    let is_found = false
    let s_recepient = $('#s_recepient')
    let opts = $('#dl_recepients')[0].childNodes
    for (let i = 0; i < opts.length; i++){
        if (opts[i].value == current_recepient.val()){
            s_recepient.html(opts[i].innerText)
            is_found = true
            break
        }
    }
    if (!is_found)
        s_recepient.html('')
}


// из contracts.js
function fill_form(this_object) {
    // Изменяем классы строк таблицы
    $('#data-table tr.table-active').each((i, el)=>{el.className = 'row'})
    $(this_object).addClass('table-active');
    let json_object = JSON.parse($('#s_current_version').html())
    // Вкинем данные в поля формы редактирования класса
    fill_object_form(json_object, true)
    // Заполним словари
    let div_wrapper_dicts = $('#div_wrapper_dicts')[0]
    if (div_wrapper_dicts){
        div_wrapper_dicts.innerHTML = ''
        let select = $('#new_dict')[0]
        select.innerHTML = ''
        for (let k in json_object){
            if (k.slice(0, 4) === 'dict'){
                let dict_id = k.slice(5)
                let header_dict = JSON.parse($('#header_dict' + dict_id).html())
                if (json_object[k]){
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
    // Заполним массивы
    fill_arrays()
    return json_object
}

// из контрактов
function tp_calc(tp_id, control_field) {
    let control_summa = (control_val) ? parseFloat(control_val) : 0
    let terms = $('input[id^="i_stage_' + tp_id + '_"]').toArray()
    let summa = 0
    terms.forEach((el) => {
        summa += (el.value) ? parseFloat(el.value) : 0
    })
    return (summa === control_summa)
}


function recount_tp(this_inp){
    clearTimeout(typingTimer);
    typingTimer = setTimeout(() => {
        let r_e = this_inp.id.match(/i_stage_(\d+)_(\d+)/)
        let tp_id = parseInt(r_e[1])
        let stage_num = parseInt(r_e[2])
        let current_val = (this_inp.value) ? parseFloat(this_inp.value) : 0
        if (current_val < 0){
            current_val = 0
            this_inp.value = 0
        }
        let delta_sum = get_tp_currrent_sum(tp_id)
        let tps = JSON.parse($('#tps').text())
        let current_tp = tps.find((el) => el.id === tp_id)
        let control_field = $('#i_float_' + current_tp.cf_val)
        let control_sum = (parseFloat(control_field.val())) ? parseFloat(control_field.val()) : 0
        let delta = delta_sum - control_sum
        function deep_diff(stage_num, delta){
            let prev_stage = $('#i_stage_' + tp_id + '_' + String(stage_num - 1))
            let prev_delay = $('#s_stage_' + tp_id + '_' + String(stage_num - 1) + '_delay')
            let prev_stage_val = (prev_stage.val()) ? parseFloat(prev_stage.val()) : 0
            let prev_delay_val = (prev_delay.text()) ? parseFloat(prev_delay.text()) : 0
            if (delta <= prev_stage_val){
                prev_stage.val(prev_stage_val - delta)
                prev_delay.text(prev_delay_val + delta * -1)
            }
            else{
                prev_delay.text(prev_delay_val + prev_stage.val() * -1)
                prev_stage.val(0)
                let deep_delta = delta - prev_stage_val
                if (stage_num > 1)
                    deep_diff(stage_num - 1, deep_delta)
                else {
                    this_inp.value = current_val - deep_delta
                    delay.text(parseFloat(delay.text()) - deep_delta)
                }
            }
        }
        let delay = $('#s_stage_' + tp_id + '_' + String(stage_num) + '_delay')
        let delay_val = (delay.text()) ? parseFloat(delay.text()) : 0
        delay.text(delay_val + delta)
        if (stage_num)
            deep_diff(stage_num, delta)
        else{
            let new_val = control_sum + delta
            control_field.val(new_val)
            recount_tps(control_field[0])
        }

    }, 1000)
}


function valid_tps(){
    clearTimeout(typingTimer)
    typingTimer = setTimeout(()=>{
        tps_valid_result = JSON.parse($('#tps2').text()).every(tp => vtp(tp))
        save_switcher('b_save')
    },  1000)
}

// iz manage-class2.js
function save_params_tree(){
    let is_right_tree = $('#chb_is_right_tree').prop('checked')
    send_form_with_param('b_save_fields_tree', is_right_tree)
}

// из контрактов
// vtp = valid techprocess procedure
function vtp(tp) {
    let is_valid = tp_calc(tp.id, tp.control_field)
        if (is_valid)
            is_valid = tp_router_calс(tp)
    return is_valid
}

// калькулятор маршрутизации
function tp_router_calс(tp) {
    let counter = 0
    let array_deltas = []
    let error_in_tp = false
    for (let i = 0; i < tp.link_map.length; i++){
        let id_dummy = '#s_stage_' + tp.id + '_' + counter + '_'
        let fact = $(id_dummy + 'fact').text()
        fact = (fact) ? parseFloat(fact) : 0
        let delay = $(id_dummy + 'delay').text()
        delay = (delay) ? parseFloat(delay) : 0
        let source_val = fact + delay
        let new_val = $('#i' + id_dummy.slice(2, id_dummy.length - 1)).val()
        new_val = (new_val) ? parseFloat(new_val) : 0
        let delta = new_val - source_val
        if (delta * -1 > fact){
            error_in_tp = true
            break
        }
        let dict_delta = {'stage': tp.link_map[i].name, 'delta': delta, 'children': tp.link_map[i].children}
        array_deltas.push(dict_delta)
        counter++
    }
    if (error_in_tp) return false
    else
        return array_deltas.every((el)=>{
            if (el.delta < 0){
                children_delta = 0
                for (let i = 0; i < el.children.length; i++){
                    let child = array_deltas.find(e => e.stage === el.children[i])
                    children_delta += child.delta
                }
                return !(el.delta + children_delta)
            }
            else return true
        })
}



function load_dict_in_object(k, obj, transact_date_time){
    let current_dict = obj[k]
    if (!current_dict) {
        current_dict = {}
        let dict_id = k.slice(5)
        let dict_header = JSON.parse($('#header_dict' + dict_id).html())
        for (let m = 0; m < dict_header.children.length; m++) {
            let dict_key = dict_header.children[m].id
            let dict_name = dict_header.children[m].name
            let dict_type = dict_header.children[m].formula
            current_dict[dict_key] = {'name': dict_name, 'type': dict_type}
        }
        obj[k] = current_dict
    }
    let dict_find = false
    let dict_hist = $('#s_dict_hist_' + k.slice(5))
    let json_hist = (dict_hist.length) ? JSON.parse(dict_hist.html()).sort((a, b) =>
        a.date_update > b.date_update ? 1 : -1) : []
    for (let j = json_hist.length - 1; j >= 0; j--) {
        if (json_hist[j]['date_update'] <= transact_date_time) {
            // Если в выбранный момент времени не было словаря, удалим текущий
            if (!json_hist[j].is_active)
                obj[k] = null
            // Иначе, заполним текущий словарь параметрами из истории
            else {
                let dict_keys = Object.keys(json_hist[j])
                for (let l in current_dict) {
                    if (dict_keys.includes(l))
                        current_dict[l].value = json_hist[j][l]
                }
            }
            dict_find = true
            break
        }
    }
    if (!dict_find)
        obj[k] = null
    return obj[k]
}

// из словарей
function fill_form(this_object) {
    // Изменяем классы строк таблицы
    $('tr').removeClass('table-active');
    $(this_object).addClass('table-active');
    // Вкинем данные в поля формы редактирования класса
    $('#i_code').val(this_object.id)
    let fields = JSON.parse($('#s_current_version').html())
    let owner = $('#i_owner')
    owner.val(fields['parent_code'])
    // Сделаем собственника нечитаемым
    if (!owner.attr('readonly'))
        owner.attr('readonly', true)
    ajax_link_def($("#parent_id").val(), owner.val(), $("#parent_type").val(), $("#s_owner")[0])
    // обернем в ссылку код
    let url = 'hist-reg?i_date_in=1970-01-01T00:00&i_filter_object=' + this_object.id + '&i_filter_class='
        + fields.parent_structure + '&s_type=dict'
    $('#a_code').attr('href', url)
    // fill_object_form(this_object, fields)
    // Заполним поля формы
    for (let key in fields){
        let val = fields[key].value
        let str_param = $('#ta_'+ key)
        let float_param = $('#i_float_' + key)
        let bool_param = $('#chb_' + key)
        let date_param = $('#i_date_' + key)
        let datetime_param = $('#i_datetime_' + key)
        let enum_param = $('#s_enum_' + key)
        let link_param = $('#i_link_' + key)
        // для строк
        if (str_param.length)
            str_param.val(val)
        // для чисел
        else if (float_param.length)
            float_param.val(val)
        // для дат
        else if (bool_param.length){
            let is_check = (val === 'True')
            bool_param.attr('checked', is_check)
        }
        // для дат
        else if (date_param.length)
            date_param.val(val)
        // для датавремени
        else if (datetime_param.length)
            datetime_param.val(val)
        // для перечислений
        else if (enum_param.length){
            for (let i = 0; i < enum_param[0].children.length; i++){
                if (enum_param[0].children[i].value === val){
                    enum_param[0].selectedIndex = i
                    break
                }
            }
        }
        // для ссылок
        else if (link_param.length){
            link_param.val(val)
            dict_link_promp(link_param[0], false)
        }
        // заполним ссылку на историю
        let url = 'hist-reg?i_date_in=1970-01-01T00:00&i_filter_object=' + this_object.id + '&i_name='
            + key + '&i_filter_class=' + fields.parent_structure + '&s_type=dict'
        $('#a_label_' + key).attr('href', url)
    }
    return fields
}

// из объект-форм
function fill_form(this_object){
    // Изменяем классы строк таблицы
    $('#data-table tr.table-active').removeClass('table-active');
    $(this_object).addClass('table-active');
    // Вкинем данные в поля формы редактирования класса
    $('#i_code').val(this_object.id)
    try{
        var json_object = JSON.parse($('#s_current_version').html())
    }
    catch(er){
        json_object = null
    }
    // Заполним данные из полей таблицы
    fill_object_form()
    // Заполним словари
    fill_dicts(json_object)
    // Заполним массивы
    fill_arrays()
    return json_object
}
