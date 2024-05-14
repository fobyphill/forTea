// Управление объектами словарей на собственной странице
var typingTimer;
window.onload = function () {
    let tr = $('tr')
    let tr_active = $('tr.table-active')
    if (tr.length){
        if (tr_active.length > 0){
            tr_active.removeClass('table-active')
            sao(tr_active[0], 'd', true)
        }
        else sao(tr[1], 'd', true)
    }
    fill_search_filter()
}

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

function new_obj(){
    // чистим
    $('.table-active').removeClass('table-active')
    $("textarea[id*='ta_']").val('')
    $("input[id*='i_']").val('')
    $("input[id*='chb_']").attr('checked', false)
    $("span[id*='s_']").html('')
    $('#i_owner').removeAttr('readonly')
    $('#b_save_dict').attr('onclick', 'send_form_with_param("b_new_dict")')
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
        else if (dict.formula === 'bool')
            pref = 'chb_'
        // вставим данные
        let current_node = $('#' + pref + id)
        if (dict.formula === 'bool')
            current_node.prop('checked', dict.default)
        else if (dict.formula === 'enum'){
            current_node[0].selectedIndex = 0
        }
        else current_node.val(dict.default)
        if (dict.formula === 'link')
            fast_get_link(current_node[0])
    })
    // Подсказка для собственника
    promp_owner($('#i_owner')[0])
}

function dict_link_promp(this_input, delay_promp=true){
    function do_this(){
        let code = this_input.value
        let id = this_input.id.slice(7)
        let header_info = JSON.parse($('#header_info' + id).text())
        let match = header_info.default.match(/^(table|contract)\.(\d+)\./)
        let datalist = $('#dl_link_' + id)
        datalist.html('')
        $.ajax({url:'gon4d',
            method:'get',
            dataType:'json',
            data: {link_type: match[1], link_id: match[2], code: code},
            success:function(data){
                if (!(typeof data === 'object' && 'error' in data)){
                    for (let i = 0; i < data.length; i++){
                        let op = document.createElement('option')
                        op.value = data[i].code
                        op.innerText = data[i].value
                        datalist.append(op)
                    }
                }
                // Заполним подсказку
                let s_def = $('#' + 's_link_' + id)
                s_def.text('')
                let arr_dl = datalist.children().toArray()
                let obj_is_correct = false
                for (let i = 0; i < arr_dl.length; i++){
                    if (code === arr_dl[i].value){
                        let url = (match[1] === 'table') ? 'manage-object' : 'contract'
                        let link_text = '<a target="_blank" href="/' + url + '?class_id=' + match[2] +
                            '&object_code=' + code + '">' + arr_dl[i].innerText + '</a>'
                        s_def.html(link_text)
                        obj_is_correct = true
                        break
                    }
                }
                if (!code)
                    obj_is_correct = true
                $('#b_save_params_dict').attr('disabled', !obj_is_correct)
            },
            error: () => {$('#i_link_def').val('Ошибка')}
        })
    }
    if (delay_promp){
        clearTimeout(typingTimer)
        typingTimer = setTimeout(do_this, 1000)
    }
    else do_this()

}

// sdlp = search_dict_link_promp
function sdlp(this_input){
    function do_this(){
        let code = this_input.value
        let id = this_input.id.slice(2)
        let header_info = JSON.parse($('#header_info' + id).text())
        let match = header_info.default.match(/^(table|contract)\.(\d+)\./)
        let datalist_id = this_input.getAttribute('list')
        let datalist = $('#' + datalist_id)
        datalist.html('')
        $.ajax({url:'gon4d',
            method:'get',
            dataType:'json',
            data: {link_type: match[1], link_id: match[2], code: code},
            success:function(data){
                if (!(typeof data === 'object' && 'error' in data)){
                    for (let i = 0; i < data.length; i++){
                        let op = document.createElement('option')
                        op.value = data[i].code
                        op.innerText = (typeof data[i].value === 'string') ? data[i].value : data[i].value.datetime_create
                        datalist.append(op)
                    }
                }
                // Заполним подсказку
                let s_def = $('#' + 's_link_' + id)
                s_def.text('')
                let arr_dl = datalist.children().toArray()
                let obj_is_correct = false
                for (let i = 0; i < arr_dl.length; i++){
                    if (code === arr_dl[i].value){
                        let url = (match[1] === 'table') ? 'manage-object' : 'contract'
                        let link_text = '<a target="_blank" href="/' + url + '?class_id=' + match[2] +
                            '&object_code=' + code + '">' + arr_dl[i].innerText + '</a>'
                        s_def.html(link_text)
                        obj_is_correct = true
                        break
                    }
                }
                if (!code)
                    obj_is_correct = true
                $('#b_save_params_dict').attr('disabled', !obj_is_correct)
            },
            error: () => {$('#i_link_def').val('Ошибка')}
        })
    }
    clearTimeout(typingTimer)
    typingTimer = setTimeout(do_this, 1000)
}