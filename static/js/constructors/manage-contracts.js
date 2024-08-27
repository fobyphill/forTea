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

function select_unit(this_unit, location) {
    $('.table-active').removeClass('table-active')
    this_unit.className = 'table-active'
    let id = (location === 'd') ? this_unit.id.slice(9) : (location === 't') ? this_unit.id.slice(7) : this_unit.id.slice(4)
    let s_info = (location === 'd') ? '#s_info_dict': (location === 't') ?  '#s_info_tp':  '#s_info'
    let unit_data = JSON.parse($(s_info + id).html())
    $('#i_id').val(unit_data.id)
    $('#i_name').val(unit_data.name)
    let type = JSON.parse($('#i_classes').val())
    $('#i_type').val(type[unit_data.formula]).attr('class', 'form-control')
    $('#i_parent').val(unit_data.parent_id)
    // чистим таблицы параметров
    $('#table_body_alias').html('')
    $('#table_body_params').html('')
    $('#dict_body_params').html('')
    // Скроем от редактирования родителя для массивов и словарей, техпроцессов
    if (['array', 'dict', 'techprocess'].includes(unit_data.formula))
        $('#i_parent').attr('readonly', true).attr('style', 'background-color: #f8f9fa')
    else $('#i_parent').attr('readonly', false).attr('style', 'background-color: white')
    $('#s_folder_class').attr('class', 'tag-invis')
    if (unit_data.formula === 'folder'){
        $('#div_class_params').attr('class', 'tag-invis')
        $('#div_alias_params').attr('class', 'tag-invis')
        $('#div_dict_params').attr('class', 'tag-invis')
        $('#div_tree_params').attr('class', 'tag-invis')
        $('#div_system_contract_params').attr('class', 'tag-invis')
    }
    // Контракт или массив
    else if (['contract', 'array'].includes(unit_data.formula)){
        // Скрываем и показываем необходимые таблицы
        $('#div_alias_params').attr('class', 'tag-invis')
        $('#div_dict_params').attr('class', 'tag-invis')
        $('#div_class_params').removeClass('tag-invis')
        $('#div_tree_params').attr('class', 'tag-invis')
        $('#div_system_contract_params').attr('class', 'tag-invis')
        let is_array = (unit_data.formula === 'array')
        if (is_array)
            $('#div_tech_processes').removeClass('tag-invis')
        $('#tree_body_params').html('')
        fill_class_params(is_array, true)
        // Для контракта покажем и заполним системные параметры
        if (!is_array){
            $('#div_system_contract_params').removeClass('tag-invis')
            fill_system_contract_params()
        }
    }
    // Словарь
    else if (unit_data.formula === 'dict'){
        $('#div_alias_params').attr('class', 'tag-invis')
        $('#div_class_params').attr('class', 'tag-invis')
        $('#div_dict_params').removeClass('tag-invis')
        $('#div_tree_params').attr('class', 'tag-invis')
        $('#div_system_contract_params').attr('class', 'tag-invis')
        // Вкинем данные полей выделенного класса
        let fields = JSON.parse($('#fields').html())
        // Заполним таблицу
        let table_body = $('#dict_body_params')[0]
        fields.forEach((field, i, array) => {
            let tr = document.createElement('tr')
            tr.id = 'param' + field.id
            tr.setAttribute('class', 'row row-param')
            tr.setAttribute('onclick', 'select_param(this, {\'is_array\': true, \'is_dict\': true, \'is_contract\': true})')
            table_body.appendChild(tr)
            // стрелки
            let td_arrows = document.createElement('td')
            td_arrows.className = 'col-0-5 text-center'
            td_arrows.style = 'padding: 0.75rem 0; font-size: large'
            tr.appendChild(td_arrows)
            if (array.length > 1){
                let inner_html = ''
                if (i != 0)
                    inner_html += '<a href="manage-contracts?i_id=' + id + '&param_id=' + field.id + '&move=up&is_dict=">&#8679;</a>'
                if (i != array.length - 1)
                    inner_html += '<a href="manage-contracts?i_id=' + id + '&param_id=' + field.id + '&move=down&is_dict=">&#8681;</a>'
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
            let tag_default
            let dict_dop = {}
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
            td_default.appendChild(tag_default)
            tr.appendChild(td_default)
            if (field.formula == 'enum'){
                tag_default.style.height = "0"
                tag_default.style.height = tag_default.scrollHeight + 5 + 'px'
            }
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
        $('#div_class_params').attr('class', 'tag-invis')
        $('#div_dict_params').attr('class', 'tag-invis')
        $('#div_alias_params').removeClass('tag-invis')
        $('#div_tree_params').attr('class', 'tag-invis')
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
    else if (unit_data.formula === 'tree'){
        $('#div_class_params').attr('class', 'tag-invis')
        $('#div_alias_params').attr('class', 'tag-invis')
        $('#div_dict_params').attr('class', 'tag-invis')
        $('#div_tree_params').attr('class', '')
        $('#tree_params').children()[1].children[0].className = 'row row-param'
        fill_class_params(false, true,true)
    }
    $('#b_save').attr('disabled', true)
}

function new_folder() {
    $('li.table-active').removeClass('table-active')
    let i_id = $('#i_id')
    let parent_id = i_id.val()
    i_id.val('')
    $('#i_name').val('')
    $('#i_parent').val(parent_id).attr('readonly', false)
    $('#i_type').attr('class', 'tag-invis')
    $('#s_folder_class').attr('class', 'form-control')
    $('#b_delete').attr('disabled', 'true')
    $('#b_save').attr('disabled', true)
    $('#div_class_params').attr('class', 'tag-invis')
    $('#div_dict_params').attr('class', 'tag-invis')
    $('#div_alias_params').attr('class', 'tag-invis')
    $('#div_tree_params').attr('class', 'tag-invis')
    $('#div_system_contract_params').attr('class', 'tag-invis')
}

window.onload = function () {
    let id = $('#i_id').val()
    let parent = $('#i_parent').val()
    let location = $('#i_loc').val()
    if ((id || parent)){
        let activate_ids = []
        if (!id)
            id = parent
        let unit
        if (location === 't')
            unit = 'unit_tp'
        else if (location === 'd')
            unit = 'unit_dict'
        else unit = 'unit'
        activate_ids.push(unit + id)
        let flag = true
        let safe_counter = 0
        while (flag){
            safe_counter++
            if (safe_counter > 500)
                break
            let s_info = (location === 'd') ? '#s_info_dict': (location === 't') ? '#s_info_tp' : '#s_info'
            let elem = $(s_info + id)
            if (elem.length){
                let object = JSON.parse(elem.html())
                if (object.parent_id){
                    activate_ids.push('unit' + object.parent_id)
                    id = object.parent_id
                    location = 'c'
                }
                else flag = false
            }
            else if (parent){
                activate_ids.push('unit' + parent)
                id = parent
                location = 'c'
            }
            else $('li')[0].click()
        }
        for (i = 0; i < activate_ids.length;){
            let temp_tag = document.getElementById(activate_ids.pop())
            if (temp_tag){
                if (activate_ids.length) show_hide_branch(temp_tag)
                else temp_tag.click()
            }
        }
    }
    else $('li')[0].click()
}

// Enter в полях блока Управления
$('input.input-manage').keypress(function(e) {
    if(e.keyCode === 13)
        send_form_with_param('b_save')
})

function new_field() {
    $('.row-param').attr('class', 'row row-param')
    let new_tr = document.createElement('tr')
    new_tr.className = 'row row-param table-active'  // Удалил активную строку
    new_tr.id = 'paramnew'
    new_tr.setAttribute('onclick', 'select_param(this)')
    $('#table_params').append(new_tr)
    $('#b_new_param').attr('disabled', true)
    // Название
    let new_name = document.createElement('td')
    new_name.className = 'col-3'
    let i_new_name = document.createElement('input')
    i_new_name.className = 'form-control'
    i_new_name.id = 'namenew'
    new_name.appendChild(i_new_name)
    new_tr.appendChild(new_name)
    // Тип
    let td_type = document.createElement('td')
    td_type.className = 'col-1-5 text-center'
    td_type.style = 'padding-left:0; padding-right: 0'
    // Создаем список типов
    let list_types = JSON.parse($('#i_types').val())
    let s_type = document.createElement('select')
    s_type.id = 's_type'
    s_type.name = 's_type'
    s_type.className = 'form-control text-center'
    s_type.style = 'padding:0'
    s_type.setAttribute('onclick', 'select_type(this)')
    list_types.forEach((elem) => {
        let opt = document.createElement('option')
        opt.id = elem
        opt.innerText = elem
        s_type.appendChild(opt)
    })
    td_type.appendChild(s_type)
    new_tr.appendChild(td_type)
    // Значение
    let td_value = document.createElement('td')
    td_value.className = 'col'
    td_value.id = 'td_new_value'
    new_tr.appendChild(td_value)
    // Умолчание
    let td_default = document.createElement('td')
    td_default.className = 'col text-center'
    td_default.id = 'td_defaultnew'
    let tag_default = document.createElement('textarea')
    tag_default.className = 'form-control'
    tag_default.style = 'min-height: 50px'
    tag_default.id = 'defaultnew'
    td_default.appendChild(tag_default)
    new_tr.appendChild(td_default)
    // Обязательный
    let td_required = document.createElement('td')
    td_required.className = 'col-1 text-center'
    let chb = document.createElement('input')
    chb.type = 'checkbox'
    chb.id = 'requirednew'
    td_required.appendChild(chb)
    // Видимость
    let td_visible = document.createElement('td')
    td_visible.className = 'col-1 text-center'
    let chb_vis = document.createElement('input')
    chb_vis.type = 'checkbox'
    chb_vis.id = 'visiblenew'
    td_visible.appendChild(chb_vis)
    new_tr.append(td_required, td_visible)
    $('#b_delete_field').attr('disabled', true)
}

function select_type(this_select) {
    $('#defaultnew').remove()
    $('#valuenew').remove()
    $('#td_new_value').html('')
    $('#s_formula_type').remove()
    // нарисуем компонент значения
    if (['enum', 'eval'].includes(this_select.value)){
        var tag_value = document.createElement('textarea')
        tag_value.style = 'min-height: 50px'
        tag_value.className = 'form-control'
        tag_value.id = 'valuenew'
        $('#td_new_value').html(tag_value)
        ta_to_editor(tag_value)
    }
    else if (this_select.value === 'link'){
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
        if (this_select.value === 'bool'){
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
        if (this_select.value === 'link')
            $('#td_defaultnew').html('<br><br>' + tag_default.outerHTML)
        else $('#td_defaultnew').html(tag_default)

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
        if (param.id.slice(0, 2) === 'tp')
            return false
        let id = param.id.slice(5)
        let name_sel = $('#name' + id)
        let type_sel = $('#type' + id)
        let dict = {}
        dict.id = parseInt(id)
        dict.name = name_sel.val()
        if (name_sel.val() !== 'Системные данные'){
            if (dict.id)
                dict.type = type_sel.html()
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
                    dict.default = (def.val().length) ? parseFloat(def.val()) : ''
                else if (dict.type === 'link')
                    dict.default = (def.val().length) ? parseInt(def.val()) : ''
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
            // для чисел добавим итоги
            if (dict.type === 'float' && dict.visible){
                let totals = []
                let tags_totals = $('span[id^="total_' + id + '"')
                tags_totals.each(function(i){
                    totals.push(tags_totals[i].id.match(/total_[\dnew]+_(\w+)/)[1])
                })
                dict.totals = totals
            }
            // для ссылок локация
            if (dict.type === 'const'){
                let json_object = JSON.parse($('#i_aliases').val())
                for (let i = 0; i < json_object.length; i++){
                    if (json_object[i].id === parseInt(dict.value)){
                        dict.location = json_object[i].location
                        break
                    }
                }
            }
            // Делэй
            let delay = {'delay': $('#delay' + id).prop('checked')}
            let handler_user = $('#i_handler_' + id)
            let handler_eval = $('#ta_handler_' + id)
            if (handler_user.length){
                if (handler_user.val())
                    delay.handler = parseInt(handler_user.val())
                else delay.handler = 0
            }
            else if (handler_eval.length)
                delay.handler = handler_eval.val()
            dict.delay = delay
        }
        // для контракта для поля Дата и время записи передадим только параметр "видимость"
        else {
            dict.visible = $('#visible' + id).prop('checked')
            dict.type = 'contract'
            dict.default = null
            dict.delay = {'delay': null, 'handler': null}
        }
        array.push(dict)
    })
    let output = JSON.stringify(array)
    send_form_with_param('b_save_fields', output)
}

function delete_field() {
    if ($('#i_id').length && $('#param_id').val())
        $('#delete_field_modal').modal('show');
}

function is_change_unit(){
    let is_change = false
    let s_info = $('#s_info' + $('#i_id').val())
    if (s_info.length){
        let unit_data = JSON.parse(s_info.html())
        if ($('#i_name').val() !== unit_data.name)
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
    if ($('#s_folder_class').val() === 'tp' && $('#s_control_field')[0].selectedIndex === 0)
        is_change = false
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
            let location = (e.location === 'contract') ? 'Контракты' : 'Справочники'
            op.innerText = e.name + ' ' + location
            data_list.appendChild(op)
        })
        i_alias.appendChild(data_list)
        i_alias.setAttribute('list', 'alias_list')
        i_alias.setAttribute('oninput', 'select_new_alias(this)')
        $('#' + td_value_id).html(i_alias)
}

// выбрать алиас из списка
function select_new_alias(this_select, field=null){
    let alias_value = parseInt(this_select.value)
    let array_alias = JSON.parse($('#i_aliases').val())
    let alias_ids = array_alias.map(a => a.id)
    let default_id = this_select.id.slice(5)
    if (alias_ids.includes(alias_value)){
        $.ajax({url:'get-alias-params',
            method:'get',
            dataType:'json',
            data: {alias_id: alias_value, is_contract: true},
            success:function(data){
                let def_new = document.createElement('select')
                def_new.className = 'form-control'
                def_new.id = 'default' + default_id
                data.forEach((e) => {
                    let op = document.createElement('option')
                    op.value = e.id
                    op.innerText = e.name
                    if (field && e.id === field.default)
                        op.setAttribute('selected', true)
                    def_new.appendChild(op)
                })
                $('#td_default' + default_id).html(def_new)
            },
            error: function () {
                $('#td_default' + default_id).html('Объект не найден')
            }
        })
    }
}

// Технические функции
// Преобразуем символьные примитивы в символы
function decodeHtml(html) {
    return $('<div>').html(html).text();
}

// Заполнить значениями системные параметры контракта
function fill_system_contract_params() {
    let params = JSON.parse($('#system_fields').text())
    params.forEach((param)=>{
        let tag_name = (param.name === 'link_map') ? 'div' : 'textarea'
        let container_tag = document.createElement(tag_name)
        let parent_td = null
        if (param.name === 'business_rule'){
            container_tag.id = 'ta_br'
            parent_td = $('#td_br')
            $('#td_br_id').text(param.id)
        }
        else if (param.name === 'link_map'){
            container_tag.id = 'div_lm'
            parent_td = $('#td_lm')
            $('#td_lm_id').text(param.id)

        }
        else if (param.name === 'trigger'){
            container_tag.id = 'ta_tr'
            parent_td = $('#td_tr')
            $('#td_tr_id').text(param.id)
        }
        else if (param.name === 'completion_condition'){
            container_tag.id = 'ta_cc'
            parent_td = $('#td_cc')
            $('#td_cc_id').text(param.id)
        }
        if (param.name === 'link_map'){
            if (parent_td)
                parent_td.append(container_tag)
            let link_map = param.value

    // рисуем дизайн
            container_tag.innerHTML = '<button class="btn btn-outline-info" onclick="acilm(\'new\')" id="b_acilm">+</button>'
            acilm(link_map)
        }
        else{
            container_tag.value = param.value
            if (parent_td)
                parent_td.append(container_tag)
        }
    })
}

function save_system_fields() {
    let sys_fields = {}
    let ta_br = $('#ta_br').val()
    sys_fields.br = (ta_br) ? ta_br : null
    sys_fields.lm = palimafos()
    let ta_tr = $('#ta_tr').val()
    sys_fields.tr = (ta_tr) ? ta_tr : null
    let ta_cc = $('#ta_cc').val()
    sys_fields.cc = (ta_cc) ? ta_cc : null
    send_form_with_param('save_system_fields', JSON.stringify(sys_fields))
}

function save_tp(){
    let dict_tp = {}
    dict_tp.business_rule = $('#ta_br').val()
    dict_tp.link_map = $('#ta_lm').val()
    dict_tp.trigger = $('#ta_tr').val()
    result = JSON.stringify(dict_tp)
    send_form_with_param('save_sys_tp', result)
}