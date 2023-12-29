function show_hide_branch(this_li) {
    let child = this_li.nextSibling.nextSibling
    if (child && child.tagName === 'UL'){
        if (child.className === 'tag-invis'){
            child.className = ''
            this_li.innerHTML = this_li.innerHTML.replace('+', '-')
            this_li.innerHTML = this_li.innerHTML.replace('folder_closed_50.png', 'folder_opened_50.png')
        }
        else if (child.className === ''){
            child.className = 'tag-invis'
            this_li.innerHTML = this_li.innerHTML.replace('-', '+')
            this_li.innerHTML = this_li.innerHTML.replace('folder_opened_50.png', 'folder_closed_50.png')
            $('#is_dict').val('false')
        }
    }
}

function select_unit(this_unit, is_dict) {
    $('.table-active').removeClass('table-active')
    this_unit.className = 'table-active'
    let id = (is_dict) ? this_unit.id.slice(9) : this_unit.id.slice(4)
    let s_info = (is_dict) ? '#s_info_dict': '#s_info'
    let unit_data = JSON.parse($(s_info + id).html())
    $('#i_id').val(id)
    $('#i_name').val(unit_data.name)
    let type = JSON.parse($('#i_classes').val())
    $('#i_type').val(type[unit_data.formula]).attr('class', 'form-control')
    let i_parent = $('#i_parent')
    i_parent.val(unit_data.parent_id)
    if (unit_data.formula === 'dict' || unit_data.formula === 'array')
        i_parent.attr('readonly', true).attr('style', 'background-color: #f8f9fa')
    else
        i_parent.attr('readonly', false).attr('style', 'background-color: white')
    $('#s_folder_class').attr('class', 'tag-invis')
    // чистим таблицы параметров
    $('#table_body_alias').html('')
    $('#table_body_params').html('')
    $('#dict_body_params').html('')
    if (unit_data.formula === 'folder'){
        $('#div_class_params').attr('class', 'tag-invis')
        $('#div_alias_params').attr('class', 'tag-invis')
        $('#div_dict_params').attr('class', 'tag-invis')
        $('#div_tree_params').attr('class', 'tag-invis')
    }
    // Справочник или массив
    else if (['table', 'array'].includes(unit_data.formula)){
        $('#tree_body_params').html('')
        $('#div_alias_params').attr('class', 'tag-invis')
        $('#div_dict_params').attr('class', 'tag-invis')
        $('#div_tree_params').attr('class', 'tag-invis')
        $('#div_class_params').removeClass('tag-invis')
        let is_array = (unit_data.formula === 'array')
        let is_tree = (unit_data.formula === 'tree')
        fill_class_params(is_array, false, is_tree)
    }
    // Словарь
    else if (unit_data.formula === 'dict'){
        $('#tree_body_params').html('')
        $('#div_alias_params').attr('class', 'tag-invis')
        $('#div_class_params').attr('class', 'tag-invis')
        $('#div_dict_params').removeClass('tag-invis')
        // Вкинем данные полей выделенного класса
        let fields = JSON.parse($('#fields').html())
        // Заполним таблицу
        let table_body = $('#dict_body_params')[0]
        fields.forEach((field, i, array) => {
            let tr = document.createElement('tr')
            tr.id = 'param' + field.id
            tr.setAttribute('class', 'row row-param')
            tr.setAttribute('onclick', 'select_param(this, {\'is_dict\': true})')
            table_body.appendChild(tr)
            // стрелки
            let td_arrows = document.createElement('td')
            td_arrows.className = 'col-0-5 text-center'
            td_arrows.style = 'padding: 0.75rem 0; font-size: large'
            tr.appendChild(td_arrows)
            if (array.length > 1){
                let inner_html = ''
                if (i != 0)
                    inner_html += '<a href="manage-class-tree?i_id=' + id + '&param_id=' + field.id + '&move=up&is_dict=">&#8679;</a>'
                if (i != array.length - 1)
                    inner_html += '<a href="manage-class-tree?i_id=' + id + '&param_id=' + field.id + '&move=down&is_dict=">&#8681;</a>'
                td_arrows.innerHTML = '<h4>' + inner_html + '</h4>'
            }
            // ID
            let td_id = document.createElement('td')
            td_id.className = 'col-0-5 text-right'
            td_id.style ="word-wrap: normal; padding: 0.75rem 0"
            td_id.innerText = field.id
            tr.appendChild(td_id)
            // Наименование
            let td_name = document.createElement('td')
            td_name.className = 'col-3'
            td_name.style = 'style="cursor: pointer; border-left: 1px solid #dee2e6"'
            let input_name = document.createElement('input')
            input_name.className = 'form-control'
            input_name.id = 'name' + field.id
            input_name.value = field.name
            td_name.appendChild(input_name)
            tr.appendChild(td_name)
            // Тип
            let td_type = document.createElement('td')
            td_type.id = 'type' + field.id
            td_type.className = 'col-1 text-center'
            td_type.innerText = field.formula
            tr.appendChild(td_type)
            // Вывод Умолчания
            let td_default = document.createElement('td')
            td_default.className = 'col text-center'
            td_default.id = 'td_default' + field.id
            tr.appendChild(td_default)
            let tag_default
            let dict_dop = {}
            let i_obj_val
            if (field.formula === 'enum'){
                let json_default = field.default
                tag_default = document.createElement('textarea')
                tag_default.className = 'form-control'
                tag_default.id = 'default' + field.id
                tag_default.style = 'min-height: 50px'
                let inner_text = ''
                json_default.forEach((e, i, array) => {
                    inner_text += e
                    if (i < array.length - 1)
                        inner_text += '\n'
                })
                tag_default.value = inner_text
            }
            else if (field.formula === 'link'){
                let link_array = field.default.match(/^(table|contract)\.(\d+)\.(\d*)/)
                tag_default = document.createElement('div')
                tag_default.className = 'row'
                let class_type = (link_array[1] === 'contract') ? 'Контракт' : 'Справочник'
                let td_class_def = document.createElement('div')
                td_class_def.className = 'col text-center'
                td_class_def.innerHTML = '<b>Тип:</b> ' + class_type + ':<br /><b>ID: </b>' + link_array[2] + '<br />'
                + '<b>Название:</b>'
                $.ajax({url:'class-link',
                    method:'get',
                    dataType:'text',
                    data: {link_id: link_array[2], class_type: link_array[1]},
                    success:function(data){ td_class_def.innerHTML += data},
                })
                tag_default.appendChild(td_class_def)
                let td_object_def = document.createElement('div')
                td_object_def.className = 'col text-center'
                tag_default.appendChild(td_object_def)
                i_obj_val = document.createElement('input')
                i_obj_val.className = 'form-control'
                i_obj_val.id = 'default' + field.id
                i_obj_val.value = link_array[3]
                let datalist_id = 'dl_link_def' + field.id
                dict_dop.link_type = link_array[1]
                dict_dop.link_id = link_array[2]
                dict_dop.datalist_id = 'dl_link_def' + field.id
                dict_dop.span_default_id = 's_link_def' + field.id
                i_obj_val.setAttribute('onclick', 'click_objs_promp("' + i_obj_val.id + '", '
                    + JSON.stringify(dict_dop))
                i_obj_val.setAttribute('oninput', 'dict_objs_promp("' + link_array[1] + '", "' +
                    link_array[2] + '", this.value, "' + datalist_id + '", "s_link_def' + field.id + '")')
                i_obj_val.setAttribute('list', 'dl_link_def' + field.id)
                td_object_def.appendChild(i_obj_val)
                let dl = document.createElement('datalist')
                dl.id = 'dl_link_def' + field.id
                td_object_def.appendChild(dl)
                let s = document.createElement('span')
                s.id = 's_link_def' + field.id
                td_object_def.appendChild(s)
            }
            else {
                tag_default = document.createElement('input')
                let dict_type = {'float': 'number', 'string': 'text', 'bool': 'checkbox', 'date': 'date', 'datetime': 'datetime-local' }
                tag_default.type = dict_type[field.formula]
                tag_default.id = 'default' + field.id
                if (field.formula !== 'bool'){
                    tag_default.className = 'form-control'
                    tag_default.value = field.default
                }
                else {
                    let def_bool = (field.default === 'True')
                    tag_default.checked = def_bool
                }
            }
            if (field.formula === 'enum'){
                tag_default.style.height = "0"
                tag_default.style.height = tag_default.scrollHeight + 5 + 'px'
            }
            td_default.appendChild(tag_default)
            // для ссылок словарей после добавления тега добавим в него подсказки
            if (field.formula === 'link')
                dict_objs_promp(dict_dop.link_type, dict_dop.link_id, i_obj_val.value, dict_dop.datalist_id,
                                dict_dop.span_default_id, false)
            // Видимый
            let td_visible = document.createElement('td')
            td_visible.className = 'col-1 text-center'
            tr.appendChild(td_visible)
            let chb_vis = document.createElement('input')
            chb_vis.id = 'visible' + field.id
            chb_vis.type = 'checkbox'
            if (field.is_visible)
                chb_vis.checked = true
            td_visible.appendChild(chb_vis)
        })
    }
    // алиас
    else if (unit_data.formula === 'alias') {
        $('#tree_body_params').html('')
        $('#div_class_params').attr('class', 'tag-invis')
        $('#div_dict_params').attr('class', 'tag-invis')
        $('#div_alias_params').removeClass('tag-invis')
        $('#table_body_params').html('')
        // Вкинем данные полей выделенного класса
        let fields = JSON.parse($('#fields').html())
        // Заполним таблицу
        let table_body = $('#table_body_alias')[0]
        table_body.innerHTML = ''
        fields.forEach((field) => {
            let tr = document.createElement('tr')
            tr.id = 'param' + field.id
            tr.setAttribute('class', 'row row-param')
            tr.setAttribute('onclick', 'select_alias(this)')
            // ID
            let td_id = document.createElement('td')
            td_id.className = 'col-1 text-right'
            td_id.innerText = field.id
            tr.appendChild(td_id)
            // Наименование
            let td_name = document.createElement('td')
            td_name.className = 'col-4'
            td_name.style = 'style="cursor: pointer; border-left: 1px solid #dee2e6"'
            let input_name = document.createElement('input')
            input_name.className = 'form-control'
            input_name.id = 'name' + field.id
            input_name.value = field.name
            td_name.appendChild(input_name)
            tr.appendChild(td_name)
            // Вывод значения
            let td_value = document.createElement('td')
            td_value.className = 'col'
            let input_val = document.createElement('textarea')
            input_val.style = 'min-height: 50px'
            input_val.className = 'form-control'
            input_val.id = 'value' + field.id
            let value = decodeHtml(field.value)
            input_val.value = value
            td_value.appendChild(input_val)
            tr.appendChild(td_value)
            table_body.appendChild(tr)
        })
    }
    // дерево
    else{
        $('#div_class_params').attr('class', 'tag-invis')
        $('#div_alias_params').attr('class', 'tag-invis')
        $('#div_dict_params').attr('class', 'tag-invis')
        $('#div_tree_params').attr('class', '')
        $('#tree_params').children()[1].children[0].className = 'row row-param'
        fill_class_params(false, false,true)
    }
    $('#b_save').attr('disabled', true)
}

function new_folder() {
    $('li.table-active').removeClass('table-active')
    let i_id = $('#i_id')
    let parent_id = i_id.val()
    i_id.val('')
    $('#i_name').val('')
    $('#i_parent').val(parent_id)
    $('#i_type').attr('class', 'tag-invis')
    $('#i_parent').attr('readonly', false)
    $('#s_folder_class').attr('class', 'form-control')
    $('#b_delete').attr('disabled', 'true')
    $('#b_save').attr('disabled', true)
    $('#div_class_params').attr('class', 'tag-invis')
    $('#div_tree_params').attr('class', 'tag-invis')
    $('#div_alias_params').attr('class', 'tag-invis')
    $('#div_dict_params').attr('class', 'tag-invis')
}



window.onload = function () {
    let id = $('#i_id').val()
    let parent = $('#i_parent').val()
    let is_dict = JSON.parse($('#is_dict').val())
    if ((id || parent)){
        let activate_ids = []
        if (!id)
            id = parent
        let unit = (is_dict) ? 'unit_dict' : 'unit'
        activate_ids.push(unit + id)
        let flag = true
        let safe_counter = 0
        while (flag){
            safe_counter++
            if (safe_counter > 500)
                break
            let s_info = (is_dict) ? '#s_info_dict': '#s_info'
            let elem = $(s_info + id)
            if (elem.length){
                let object = JSON.parse(elem.html())
                if (object.parent_id){
                    activate_ids.push('unit' + object.parent_id)
                    id = object.parent_id
                    is_dict = false
                }
                else flag = false
            }
            else if (parent){
                activate_ids.push('unit' + parent)
                id = parent
                is_dict = false
            }
            else $('li')[0].click()
        }
        for (i = 0; i < activate_ids.length;){
            let temp_tag = document.getElementById(activate_ids.pop())
            if (temp_tag){
                if (activate_ids.length)
                    show_hide_branch(temp_tag)
                else
                    temp_tag.click()
            }
        }
    }
    else $('li')[0].click()
}

// Enter в полях блока Управления
$('input.input-manage').keypress(function(e) {
    if(e.keyCode === 13)
        $('#b_save')[0].click()
});

function select_type(this_select) {
    $('#defaultnew').remove()
    $('#valuenew').remove()
    $('#s_formula_type').remove()
    let td_new_value = $('#td_new_value')[0]
    td_new_value.innerHTML = ''
    // нарисуем компонент значения
    if (['enum', 'eval'].includes(this_select.value)){
        var tag_value = document.createElement('textarea')
        tag_value.style = 'min-height: 50px'
        tag_value.className = 'form-control'
        tag_value.id = 'valuenew'
        $('#td_new_value').html(tag_value)
        ta_to_editor(tag_value)
    }
    else if (this_select.value === 'link' || this_select.value === 'const'){
        // Первая радиокнопка
        let div_chb_table = document.createElement('div')
        div_chb_table.className = 'form-check'
        td_new_value.appendChild(div_chb_table)
        let chb_table = document.createElement('input')
        chb_table.type = 'radio'
        chb_table.name = 'chb_link_type'
        chb_table.value = 'table'
        chb_table.id = 'chb_link_table'
        chb_table.setAttribute('checked', true)
        chb_table.className = 'form-check-input'
        chb_table.setAttribute('onclick', 'ajax_link_value()')
        div_chb_table.appendChild(chb_table)
        let label_chb_table = document.createElement('label')
        label_chb_table.setAttribute('for', 'chb_link_table')
        label_chb_table.innerText = 'Справочник'
        label_chb_table.className = 'form-check-label'
        div_chb_table.appendChild(label_chb_table)
        // Вторая радиокнопка
        let div_chb_contract = document.createElement('div')
        div_chb_contract.className = 'form-check'
        td_new_value.appendChild(div_chb_contract)
        let chb_contract = document.createElement('input')
        chb_contract.type = 'radio'
        chb_contract.name = 'chb_link_type'
        chb_contract.value = 'contract'
        chb_contract.id = 'chb_link_contract'
        chb_contract.className = 'form-check-input'
        chb_contract.setAttribute('onclick', 'ajax_link_value()')
        div_chb_contract.appendChild(chb_contract)
        let label_chb_contract = document.createElement('label')
        label_chb_contract.setAttribute('for', 'chb_link_contract')
        label_chb_contract.innerText = 'Контракт'
        label_chb_contract.className = 'form-check-label'
        div_chb_contract.appendChild(label_chb_contract)
        // Поле ввода
        let input_value = document.createElement('input')
        input_value.type = 'number'
        input_value.id = 'valuenew'
        input_value.className = 'form-control'
        input_value.setAttribute('oninput', 'ajax_link_value()')
        td_new_value.appendChild(input_value)
        // Спан подсказки
        let span_value = document.createElement('span')
        span_value.id = 'span_new_value'
        td_new_value.appendChild(span_value)
    }
    // нарисуем компонент умолчания
    if (!['eval', 'file', 'enum'].includes(this_select.value)){
        $('#td_defaultnew').attr('class', 'col text-center')
        let tag_default = document.createElement('input')
        tag_default.id = 'defaultnew'
        if (this_select.value == 'bool'){
            tag_default.type = 'checkbox'
        }
        else{
            tag_default.className = 'form-control'
            if (['float', 'link'].includes(this_select.value))
                tag_default.type = 'number'
            else if (this_select.value === 'datetime')
                tag_default.type = 'datetime-local'
            else if (this_select.value === 'date')
                tag_default.type = 'date'
        }
        $('#td_defaultnew').html(tag_default)
    }
    else $('#td_defaultnew').attr('class', 'tag-invis')
    if (this_select.value === 'const'){
        fill_aliases('td_new_value', 'valuenew')
    }
    // Добавим в поле для умолчания спан и аякс для ссылок
    if (this_select.value === 'link'){
        let default_value = $('#defaultnew')[0]
        default_value.setAttribute('oninput', 'ajax_link_default()')
        let span_default_new = document.createElement('span')
        span_default_new.id = 'span_default_new'
        let td_default_new =  $('#td_defaultnew')
        td_default_new.append(span_default_new)
        let br = document.createElement('br')
        let br2 = br.cloneNode()
        td_default_new[0].insertBefore(br, default_value)
        td_default_new[0].insertBefore(br2, br)
    }
    // Для формул добавим выпадающий список с типами формул
    if (this_select.value === 'eval'){
        let select_formula_type = document.createElement('select')
        select_formula_type.className = 'form-control'
        select_formula_type.style.width = 'auto'
        select_formula_type.style.padding = 0
        select_formula_type.id = 's_formula_type'
        let list_formula_types = {'on_view': 'При просмотре', 'on_click': 'При нажатии', 'on_update': 'При обновлении'}
        for (let lft in list_formula_types){
            let op = document.createElement('option')
            op.value = lft
            op.innerText = list_formula_types[lft]
            select_formula_type.appendChild(op)
        }
        let my_node = $('#s_type')[0]
        let parent_node = my_node.parentNode
        parent_node.insertBefore(select_formula_type, my_node.nextSibling)
    }
}

function save_fields() {
    let array = []
    $('.row-param').toArray().forEach((param) => {
        let id = param.id.slice(5)
        let dict = {}
        dict.id = parseInt(id)
        dict.name = $('#name' + id).val()
        if (dict.id)
            dict.type = $('#type' + id).html()
        else dict.type = $('#s_type').val()
        if ($('#required' + id).prop('checked'))
            dict.is_required = true
        else dict.is_required = false
        // Значение
        let val = $('#value' + id)
        if (val.length){
            if (val[0].type === 'checkbox')
                dict.value = val.prop('checked')
            else
                dict.value = val.val()
        }
        else dict.value = ''
        // Умолчание
        let def = $('#default' + id)
        if (def.length){
            if (def[0].type === 'checkbox')
                dict.default = def.prop('checked')
            else if (dict.type === 'float')
                dict.default = parseFloat(def.val())
            else if (dict.type === 'link')
                dict.default = parseInt(def.val())
            else if (dict.type === 'const')
                dict.default = parseInt(def.val())
            else
                dict.default = def.val()
        }
        else dict.default = ''
        // для формул заполним умолчание отдельно
        let formula_type = $('#' + param.id + ' #s_formula_type')
        if (formula_type.length){
            dict.default = formula_type.val()
        }
        // Видимость
        dict.visible = $('#visible' + id).prop('checked')
        // для ссылок локация
        if (dict.type === 'const'){
            let json_object = JSON.parse($('#i_aliases').val())
            for (let i = 0; i < json_object.length; i++){
                if (json_object[i].id == parseInt(dict.value)){
                    dict.location = json_object[i].location
                    break
                }
            }
        }
        // Делэй
        dict.delay = $('#delay' + id).prop('checked')
        // Если делэй включен - передадим и его параметры
        if (dict.delay){
            let handler = $('#i_handler_' + id)
            if (handler.length)
                dict.handler = handler.val() * 1
            else{
                handler = $('#ta_handler_' + id)
                dict.handler = handler.val()
            }
        }
        array.push(dict)
    })
    let output = JSON.stringify(array)
    send_form_with_param('b_save_fields', output)
}

function is_change_unit(){
    let is_change = false
    if ($('#s_info' + $('#i_id').val()).length){
        let unit_data = JSON.parse($('#s_info' + $('#i_id').val()).html())
        if ($('#i_name').val() != unit_data.name)
            is_change = true
        else if (isNaN(parseInt(unit_data.parent_id))){
            if ($.isNumeric($('#i_parent').val()))
                is_change = true
        }
        else if (parseInt($('#i_parent').val()) != parseInt(unit_data.parent_id))
            is_change = true
    }
    else if ($('#i_name').val())
        is_change = true
    $('#b_save').attr('disabled', !is_change)
}

// Управление алиасами
function new_alias() {
    $('.row-param').attr('class', 'row row-param')
    let new_tr = document.createElement('tr') // Удалил активную строку
    new_tr.className = 'row row-param table-active'
    new_tr.id = 'aliasnew'
    new_tr.setAttribute('onclick', 'select_alias(this)')
    // Название
    let new_name = document.createElement('td')
    new_name.className = 'col-5'
    let i_new_name = document.createElement('input')
    i_new_name.className = 'form-control'
    i_new_name.id = 'namenew'
    new_name.appendChild(i_new_name)
    new_tr.appendChild(new_name)
    // Значение
    let td_value = document.createElement('td')
    td_value.className = 'col'
    new_tr.appendChild(td_value)
    let ta_value = document.createElement('textarea')
    ta_value.className = 'form-control'
    ta_value.id = 'valuenew'
    ta_value.style = 'min-height: 50px'
    td_value.appendChild(ta_value)
    $('#table_body_alias').append(new_tr)
    $('#b_new_alias').attr('disabled', true)
    $('#b_delete_alias').attr('disabled', true)
}

function select_alias(this_elem) {
    $('.row-param').attr('class', 'row row-param')
    this_elem.setAttribute('class', 'row row-param table-active')
    $('#param_id').val(this_elem.id.slice(5))
    if (this_elem.id === 'aliasnew')
        $('#b_delete_alias').attr('disabled', true)
    else $('#b_delete_alias').attr('disabled', false)
}

function save_alias(){
    let array = []
    $('.row-param').toArray().forEach((param) => {
        let id = param.id.slice(5)
        let dict = {}
        dict.id = parseInt(id)
        dict.name = $('#name' + id).val()
        // Значение
        dict.value = $('#value' + id).val()
        array.push(dict)
    })
    let output = JSON.stringify(array)
    send_form_with_param('b_save_alias', output)
}

function delete_alias() {
    if ($('#i_id').length && $('#param_id').val())
        $('#delete_alias_modal').modal('show');
}

function fill_aliases(td_value_id, i_id) {
    let i_alias = document.createElement('input')
        i_alias.className = 'form-control'
        i_alias.id = i_id
        i_alias.name = i_id
        let data_list = document.createElement('datalist')
        data_list.id = 'alias_list'
        let array_alias = JSON.parse($('#i_aliases').val())
        array_alias.forEach((e) =>{
            let op = document.createElement('option')
            op.value = e.id
            let location = (e.location === 'table') ? 'Справочники' : 'Контракты'
            op.innerText = e.name + ' ' + location
            data_list.appendChild(op)
        })
        i_alias.appendChild(data_list)
        i_alias.setAttribute('list', 'alias_list')
        i_alias.setAttribute('oninput', 'select_new_alias(this)')
        $('#' + td_value_id).html(i_alias)
}

// Технические функции
// Преобразуем символьные примитивы в символы
function decodeHtml(html) {
    return $('<div>').html(html).text();
}

// сохранить системные параметры
function save_system_fields(){
    let chb = $('#chb_use_delay').is(':checked')
    send_form_with_param('b_save_system_fields', chb)
}



