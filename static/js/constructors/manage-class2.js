var typingTimer;
var typingTimer2

function new_field_dict(){
    $('#b_new_param_dict').attr('disabled', true)
    $('.row-param').attr('class', 'row row-param')
    let new_tr = document.createElement('tr')
    new_tr.className = 'row row-param table-active'  // Удалил активную строку
    new_tr.id = 'paramnew'
    new_tr.setAttribute('onclick', 'select_param(this, {\'is_array\': true, \'is_contract\': true})')
    $('#dict_body_params').append(new_tr)
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
    let list_types_all = JSON.parse($('#i_types').val())
    let list_types = []
    list_types_all.forEach((el, i) =>{
        if (!['eval', 'const', 'file'].includes(el))
            list_types.push(el)
    })
    let s_type = document.createElement('select')
    s_type.id = 's_type'
    s_type.name = 's_type'
    s_type.className = 'form-control text-center'
    s_type.style = 'padding:0'
    s_type.setAttribute('onclick', 'select_type_dict(this)')
    list_types.forEach((elem) => {
        let opt = document.createElement('option')
        opt.id = elem
        opt.innerText = elem
        s_type.appendChild(opt)
    })
    td_type.appendChild(s_type)
    new_tr.appendChild(td_type)
    // Умолчание
    let td_default = document.createElement('td')
    td_default.className = 'col'
    td_default.id = 'td_defaultnew'
    let tag_default = document.createElement('input')
    tag_default.className = 'form-control'
    tag_default.id = 'defaultnew'
    td_default.appendChild(tag_default)
    new_tr.appendChild(td_default)
    // Видимость
    let td_visible = document.createElement('td')
    td_visible.className = 'col-1 text-center'
    let chb_vis = document.createElement('input')
    chb_vis.type = 'checkbox'
    chb_vis.id = 'visiblenew'
    td_visible.appendChild(chb_vis)
    new_tr.append(td_visible)
    $('#b_delete_field').attr('disabled', true)
    $('#b_delete_field_dict').attr('disabled', true)

}

function select_type_dict(this_select){
    $('#defaultnew').remove()
    let tag_default
    if (this_select.value === 'link'){
        tag_default = document.createElement('div')
        tag_default.className = 'row'
        let div_type = document.createElement('div')
        div_type.className = 'col'
        tag_default.appendChild(div_type)
        div_type.innerHTML = '<div class="form-check"><input type="radio" name="chb_link_type" value="table"' +
            ' id="chb_link_table" checked="true" class="form-check-input" onclick="show_class_val()">' +
            '<label for="chb_link_table"class="form-check-label">Справочник</label></div>' +
            '<div class="form-check"><input type="radio" name="chb_link_type" value="contract" id="chb_link_contract"' +
            ' class="form-check-input" onclick="show_class_val()">' +
            '<label for="chb_link_contract" class="form-check-label">Контракт</label></div>'
        let div_val = document.createElement('div')
        div_val.className = 'col'
        tag_default.appendChild(div_val)
        div_val.innerHTML = '<input class="form-control" id="i_link_val" list="dl_link_val" oninput="show_class_val()">' +
            '<datalist id="dl_link_val"></datalist><span id="s_link_val">'
        let div_def = document.createElement('div')
        div_def.className = 'col'
        tag_default.appendChild(div_def)
        let link_type = 'table'
        div_def.innerHTML = '<input class="form-control" id="i_link_def" list="dl_link_def" onclick="cop_new_req()" ' +
            'oninput="dop_prepare_new_req()"><datalist id="dl_link_def"></datalist><span id="s_link_def">'
    }
    else if (this_select.value === 'enum'){
        tag_default = document.createElement('textarea')
        tag_default.id = 'defaultnew'
        tag_default.style = 'min-height: 50px'
        tag_default.className = 'form-control'
    }
    else{
        tag_default = document.createElement('input')
        tag_default.id = 'defaultnew'
        if (this_select.value === 'bool'){
            tag_default.type = 'checkbox'
            $('#td_defaultnew').addClass('text-center')
        }
        else{
            tag_default.className = 'form-control'
            if (this_select.value === 'float')
                tag_default.type = 'number'
            else if (this_select.value === 'datetime')
                tag_default.type = 'datetime-local'
            else if (this_select.value === 'date')
                tag_default.type = 'date'
        }
    }
    $('#td_defaultnew').html(tag_default)
    if (this_select.value === 'link')
        show_class_val()
}

function save_params_dict() {
    let array = []
    $('.row-param').toArray().forEach((param) => {
        let id = param.id.slice(5)
        let dict = {}
        dict.id = parseInt(id)
        dict.name = $('#name' + id).val()
        if (dict.id)
            dict.type = $('#type' + id).html()
        else dict.type = $('#s_type').val()
        // Умолчание
        let new_param_type = $('#s_type')
        // для нового параметра - ссылки
        if (id === 'new' && new_param_type.val() === 'link'){
            dict.default = $('input[name="chb_link_type"]:checked').val() + '.' + $('#i_link_val').val() + '.'
                + $('#i_link_def').val()
        }
        // для остального
        else{
            let def = $('#default' + id)
            if (def.length){
                if (def[0].type === 'checkbox')
                    dict.default = def.prop('checked')
                else
                    dict.default = def.val()
            }
            else dict.default = ''
        }
        // Видимость
        dict.visible = $('#visible' + id).prop('checked')
        array.push(dict)
    })
    let output = JSON.stringify(array)
    send_form_with_param('b_save_fields_dict', output)
}

function select_param(this_tr, options={})  {
    $('.row-param').attr('class', 'row row-param')
    this_tr.setAttribute('class', 'row row-param table-active')
    $('#param_id').val(this_tr.id.slice(5))
    let is_array = ('is_array' in options && options.is_array)
    let is_dict = ('is_dict' in options && options.is_dict)
    let is_contract = ('is_contract' in options && options.is_contract)
    let is_tree = ('is_tree' in options && options.is_tree)
    let is_stage = ('is_stage' in options && options.is_stage)
    if (is_dict | is_tree){
        if (this_tr.id === 'paramnew'){
            $('#b_delete_field_dict').attr('disabled', true)
            $('#b_delete_field_tree').attr('disabled', true)
        }

        else{
            $('#b_delete_field_dict').attr('disabled', false)
            $('#b_delete_field_tree').attr('disabled', false)
        }
    }
    // для контрактов
    else if (is_contract && !is_array){
        if ($('#name' + this_tr.id.slice(5)).val() === 'system_data' || this_tr.id === 'paramnew' ||
            $('#type' + this_tr.id.slice(5)).html() === 'array')
            $('#b_delete_field').attr('disabled', true)
        else $('#b_delete_field').attr('disabled', false)
    }
    // для стадий тп
    else if (is_stage)
        $('#b_delete_stage').attr('disabled', (this_tr.id === 'new'))
    // для справочников и массивов
    else {
       let nec_field = is_array ? 'Собственник' : 'Наименование'
    if ($('#name' + this_tr.id.slice(5)).val() === nec_field || this_tr.id === 'paramnew'
        || this_tr.children[3].innerText === 'array')
        $('#b_delete_field').attr('disabled', true)
    else $('#b_delete_field').attr('disabled', false)
    }
}

function delete_field(is_dict=false) {
    if ($('#i_id').length && $('#param_id').val()){
        if (is_dict)
            $('#delete_field_dict_modal').modal('show');
        else
            $('#delete_field_modal').modal('show');
    }
}


// Enter в поле поиска
$('#i_search').keypress(function(e) {
    if(e.keyCode === 13)
        full_search_in_tree()
});



function new_field(is_contract, is_tree=false) {
    $('.row-param').attr('class', 'row row-param')
    let new_tr = document.createElement('tr')
    new_tr.className = 'row row-param table-active'  // Удалил активную строку
    new_tr.id = 'paramnew'
    let sel_param = 'select_param(this, {\'is_contract\': ' + is_contract + ', \'is_tree\': ' + is_tree + '})'
    new_tr.setAttribute('onclick', sel_param)
    let table_name = (is_tree) ? 'tree_params' : 'table_params'
    $('#' + table_name).append(new_tr)
    let b_new_field = (is_tree) ? 'b_tree_new_param' : 'b_new_param'
    $('#b' + b_new_field).attr('disabled', true)
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
    s_type.setAttribute('onchange', 'select_type(this)')
    list_types.forEach((elem) => {
        if (is_tree && elem === 'file')
            return false
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
    td_required.className = 'col-0-5 text-center'
    let chb = document.createElement('input')
    chb.type = 'checkbox'
    chb.id = 'requirednew'
    td_required.appendChild(chb)
    // Видимость
    let td_visible = document.createElement('td')
    td_visible.className = 'col-0-5 text-center'
    let chb_vis = document.createElement('input')
    chb_vis.type = 'checkbox'
    chb_vis.id = 'visiblenew'
    chb_vis.setAttribute('onclick', 'set_totals_settings(this, ' + is_contract + ')')
    td_visible.appendChild(chb_vis)
    new_tr.append(td_required, td_visible)
    if (is_tree){
        $('#b_delete_field_tree').attr('disabled', true)
        $('#b_tree_new_param').attr('disabled', true)
    }
    else{
        $('#b_delete_field').attr('disabled', true)
        $('#b_new_param').attr('disabled', true)
    }
    // делэй
    if (!is_tree){
        let td_delay = document.createElement('td')
        td_delay.className = 'col-0-5 text-center'
        let chb_delay = document.createElement('input')
        chb_delay.type = 'checkbox'
        chb_delay.id = 'delaynew'
        chb_delay.setAttribute('onclick', 'set_delay_settings(this)')
        td_delay.appendChild(chb_delay)
        new_tr.appendChild(td_delay)
    }
}

// выбрать алиас из списка
function select_new_alias(this_select, field = null) {
    let json_object = JSON.parse($('#i_aliases').val())
    let is_contract = json_object.some((e) => {
        return e.id === parseInt(this_select.value) && e.location === 'contract'
    })
    let alias_value = parseInt(this_select.value)
    let array_alias = JSON.parse($('#i_aliases').val())
    let alias_ids = array_alias.map(a => a.id)
    let default_id = this_select.id.slice(5)
    if (alias_ids.includes(alias_value)) {
        $.ajax({
            url: 'get-alias-params',
            method: 'get',
            dataType: 'json',
            data: {alias_id: alias_value, is_contract: is_contract},
            success: function (data) {
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

function fill_class_params(is_array, is_contract=false, is_tree=false){
    // чистим таблицу алиасов
    $('#table_body_alias').html('')
    // Вкинем данные полей выделенного класса
    let fields = JSON.parse($('#fields').html())
    // Заполним таблицу
    let table_name = (is_tree) ? 'tree_body_params' : 'table_body_params'
    let table_body = $('#' + table_name)[0]
    if (is_tree){
        let first_child = table_body.children[0]
        let second_child = table_body.children[1]
        table_body.innerHTML = ''
        table_body.appendChild(first_child)
        table_body.appendChild(second_child)
    }
    else {
        table_body.innerHTML = ''

    }
    fields.forEach((field, i, array) => {
        if (is_tree){ // Для дерева запилим вывод поля "правильное дерево"
            if (field.name === 'is_right_tree' && field.formula === 'bool'){
                $('#param_is_right').attr('id', 'param' + field.id)
                $('#param_id_is_right').html(field.id)
                $('#name_is_right').attr('id', 'name' + field.id)
                $('#type_is_right').attr('id', 'type' + field.id)
                $('#value_is_right').attr('id', 'value' + field.id).prop('checked', field.value).attr('checked', field.value)
                $('#default_is_right').attr('id', 'default' + field.id).prop('checked', false).attr('checked', false)
                $('#required_is_right').attr('id', 'required' + field.id)
                $('#visible_is_right').attr('id', 'visible' + field.id)
                return false
            }
            if (field.name === 'name' && field.formula === 'string'){
                $('#td_tree_name_id').text(field.id)
                return false
            }
        }
        let tr = document.createElement('tr')
        tr.id = 'param' + field.id
        tr.setAttribute('class', 'row row-param')
        let onclk_vl = 'select_param(this, {\'is_array\': ' + is_array + ', \'is_contract\': ' + is_contract +
            ', \'is_tree\': ' + is_tree + '})'
        tr.setAttribute('onclick', onclk_vl)
        table_body.appendChild(tr)
        // стрелки
        let td_arrows = document.createElement('td')
        td_arrows.className = 'col-0-5 text-center'
        td_arrows.style = 'padding: 0.75rem 0; font-size: large'
        tr.appendChild(td_arrows)
        let current_url = (is_contract) ? 'manage-contracts' : 'manage-class-tree'
        if (array.length > 1){
            let inner_html = ''
            if (i !== 0)
                inner_html += '<a href="' + current_url + '?i_id=' + field.parent_id + '&param_id=' + field.id + '&move=up">&#8679;</a>'
            if (i !== array.length - 1)
                inner_html += '<a href="' + current_url + '?i_id=' + field.parent_id + '&param_id=' + field.id + '&move=down">&#8681;</a>'
            td_arrows.innerHTML = '<h4>' + inner_html + '</h4>'
        }
        // ID
        let td_id = document.createElement('td')
        td_id.className = 'col-0-5 text-right'
        td_id.style = "word-wrap: normal; padding: 0.75rem 0"
        td_id.innerText = field.id
        tr.appendChild(td_id)
        // Наименование
        let td_name = document.createElement('td')
        td_name.className = 'col-3'
        td_name.style = 'style="cursor: pointer; border-left: 1px solid #dee2e6"'
        if (field.formula === 'array')
            td_name.innerText = field.name
        else {
            let input_name = document.createElement('input')
            input_name.className = 'form-control'
            input_name.id = 'name' + field.id
            input_name.value = field.name
            if ((is_array && field.name === 'Собственник')
                || (is_contract && field.name === 'system_data' && !is_array)
                || (!is_array && !is_contract && field.name === 'Наименование')){
                input_name.setAttribute('readonly', true)
                if (is_contract && !is_array)
                    input_name.value = 'Системные данные'
            }
            td_name.appendChild(input_name)
        }
        tr.appendChild(td_name)
        // Тип
        let td_type = document.createElement('td')
        td_type.className = 'col-1 text-center'
        tr.appendChild(td_type)
        let div_type = document.createElement('div')
        div_type.id = 'type' + field.id
        div_type.innerText = field.formula
        td_type.appendChild(div_type)
        // Вывод значения
        var td_value = document.createElement('td')
        td_value.className = 'col text-center'
        td_value.id = 'td_value' + field.id
        tr.appendChild(td_value)
        if (field.formula === 'link'){
            // Тип
            td_value.innerHTML += '<b>Тип: </b>'
            let span_type = document.createElement('span')
            span_type.id = 'span_type_def' + field.id
            var array_value = field.value.match(/(.+)\.(.+$)/)
            span_type.innerText = (array_value[1] === 'table')? 'Справочник' : 'Контракт'
            td_value.innerHTML += span_type.outerHTML
            // ID
            let span_id = document.createElement('span')
            span_id.id = 'span_id_def' + field.id
            span_id.innerText = array_value[2]
            td_value.innerHTML += '<br><b>ID:</b> ' + span_id.outerHTML
            // Название
            var span_name = document.createElement('span')
            span_name.id = 'span_name_def' + field.id
            td_value.innerHTML += '<br><b>Название: </b> '
            td_value.appendChild(span_name)
            if (array_value[2]){
                $.ajax({url:'class-link',
                    method:'get',
                    dataType:'text',
                    data: {link_id: array_value[2], class_type: array_value[1]},
                    success:function(data){
                        span_name.innerText = data
                        },
                })
            }
        }
        else if (['enum', 'eval'].includes(field.formula)) {
            var input_val = document.createElement('textarea')
            input_val.style = 'min-height: 50px'
            input_val.className = 'form-control'
            input_val.id = 'value' + field.id
            // Выывод значения для собственника
            if (field.name === 'Собственник')
                input_val.setAttribute('readOnly', true)
            let value = decodeHtml(field.value)
            if (field.formula === 'enum') {
                value = field.value.join('\n')
            }
            input_val.value = value
            td_value.appendChild(input_val)
        }
        // Вывод значения для алиаса
        else if (field.formula === 'const'){
            let tag_value = document.createElement('input')
            tag_value.className = 'form-control'
            tag_value.id = 'value' + field.id
            td_value.appendChild(tag_value)
            tag_value.value = field.value
            tag_value.setAttribute('readonly', true)
            select_new_alias(tag_value, field)
        }
        // Вывод Умолчания
        if (!['eval', 'file', 'enum'].includes(field.formula)){
            let td_default = document.createElement('td')
            td_default.className = 'col-2 text-center'
            td_default.id = 'td_default' + field.id
            tr.appendChild(td_default)
            if ( !['eval', 'const', 'array'].includes(field.formula) && !['Наименование', 'system_data'].includes(field.name)) {
                var tag_default = document.createElement('input')
                tag_default.id = 'default' + field.id
                if (field.formula !== 'bool')
                    tag_default.className = 'form-control'
                tag_default.value = field.default
                if (field.formula === 'date')
                    tag_default.type = 'date'
                else if (field.formula === 'datetime')
                    tag_default.type = 'datetime-local'
                else if (['float', 'link'].includes(field.formula)){
                    tag_default.type = 'number'
                    // для ссылок добавим аякс
                    if (field.formula === 'link'){
                        tag_default.setAttribute('oninput', 'change_default(this)')
                        var span_default = document.createElement('span')
                        span_default.id = 'span_default' + field.id
                        td_default.appendChild(span_default)
                        ajax_link_def(array_value[2], tag_default.value, array_value[1], span_default)
                    }
                }
                else if (field.formula === 'bool'){
                    tag_default.type = 'checkbox'
                    if (field.default === 'True')
                        tag_default.setAttribute('checked', true)
                }
                td_default.appendChild(tag_default)
            }
            else if (field.formula === 'const') {
                let tag_default = document.createElement('select')
                tag_default.id = 'default' + field.id
                tag_default.className = 'form-control'
                td_default.appendChild(tag_default)
                let is_contract = (field.value[0] === 'c')
                let alias_id = field.value.match(/.*\.(\d+)/,)[1]
                $.ajax({
                    url: 'retreive-const-list',
                    method: 'get',
                    dataType: 'json',
                    data: {alias_id: alias_id, is_contract: is_contract},
                    success: function (data) {
                        data.forEach((e) => {
                            let op = document.createElement('option')
                            op.value = e.id
                            op.innerText = e.name
                            if (field && e.id === parseInt(field.default))
                                op.setAttribute('selected', true)
                            tag_default.appendChild(op)
                        })
                    },
                    error: function () {
                        tag_default.innerText = 'Объект не найден'
                    }
                })
            }
        }
        // Умолчание для формул
        else if (field.formula === 'eval'){
            let select_formula_type = document.createElement('select')
            select_formula_type.className = 'form-control'
            select_formula_type.style.float = 'right'
            select_formula_type.style.width = 'auto'
            select_formula_type.style.padding = 0
            select_formula_type.id = 's_formula_type'
            let list_values_ft = {'on_view': 'При просмотре', 'on_click': 'При нажатии', 'on_update': 'При обновлении'}
            for (let lv in list_values_ft){
                let op = document.createElement('option')
                op.value = lv
                op.innerText = list_values_ft[lv]
                if (field.default === lv)
                    op.setAttribute('selected', true)
                select_formula_type.appendChild(op)
            }
            let div_type = $('#type' + field.id)[0]
            let td_type = div_type.parentNode
            td_type.innerHTML = td_type.innerHTML + '<br>'
            td_type.appendChild(select_formula_type)
        }
        // обязательный
        let td_required = document.createElement('td')
        td_required.className = 'col-0-5 text-center'
        if (field.formula !== 'array'){
            let chb = document.createElement('input')
            chb.id = 'required' + field.id
            chb.type = 'checkbox'
            chb.value = field.is_required
            if (field.is_required)
                chb.checked = true
            if ((field.name === 'Наименование' && !is_contract && !is_array && !is_tree) ||
            (field.name === 'system_data' && is_contract && !is_array && !is_tree) ||
            (field.name === 'Собственник' && is_array))
                chb.setAttribute('onclick', 'return false')
            td_required.appendChild(chb)
        }
        tr.appendChild(td_required)
        // Видимый
        let td_visible = document.createElement('td')
        td_visible.className = 'col-0-5 text-center'
        tr.appendChild(td_visible)
        if (field.formula !== 'array'){
            let chb_vis = document.createElement('input')
            chb_vis.id = 'visible' + field.id
            chb_vis.type = 'checkbox'
            chb_vis.setAttribute('onclick', 'set_totals_settings(this, ' + is_contract + ')')
            // if (field.name === 'Наименование')
            //     chb_vis.setAttribute('onclick', 'return false')
            if (field.is_visible)
                chb_vis.checked = true
            td_visible.appendChild(chb_vis)
            // Поправим размеры текстареа
            if (['enum', 'eval'].includes(field.formula)){
                input_val.style.height = "0"
                input_val.style.height = input_val.scrollHeight + 5 + 'px'
            }
        }
        // delay для контрактов
        if (is_contract){
            if (field.formula !== 'array' && !is_tree){
                let td_delay = document.createElement('td')
                td_delay.className = 'col-0-5 text-center'
                tr.appendChild(td_delay)
                let chb_delay = document.createElement('input')
                chb_delay.id = 'delay' + field.id
                chb_delay.type = 'checkbox'
                if (field.formula !== 'eval'){
                    if (field.delay && field.delay.delay)
                        chb_delay.checked = true
                    chb_delay.setAttribute('onclick', 'set_delay_settings(this, true)')
                }
                else
                    chb_delay.setAttribute('onclick', 'return false')
                if (is_contract && field.name === 'system_data' && !is_array ||
                    is_contract && field.name === 'Собственник' && is_array){
                    chb_delay.checked = false
                    chb_delay.setAttribute('onclick', 'return false')
                }
                td_delay.appendChild(chb_delay)
            }
        }
        // для справочников - delay
        else{
            if (field.formula !== 'array' && !is_tree){
                let td_delay = document.createElement('td')
                td_delay.className = 'col-0-5 text-center'
                tr.appendChild(td_delay)
                let chb_delay = document.createElement('input')
                chb_delay.id = 'delay' + field.id
                chb_delay.type = 'checkbox'
                if (field.formula !== 'eval'){
                    if (field.delay)
                        chb_delay.checked = true
                    chb_delay.setAttribute('onclick', 'set_delay_settings(this)')
                }
                else
                    chb_delay.setAttribute('onclick', 'return false')
                td_delay.appendChild(chb_delay)
            }
        }
    })
    // для дерева на контракте закинем имя
    if (is_contract && is_tree){
        let sys_props = JSON.parse($('#system_fields').text())
        for (let i = 0; i < sys_props.length; i++){
            if (sys_props[i].name === 'name'){
                $('#td_tree_name_id').text(sys_props[i].id)
                break
            }
        }
    }
    // для массива закинем техпроцессы
    if (is_array && is_contract){
        let tech_process = JSON.parse($('#system_fields').text())
        tech_process.forEach((tp, i)=>{
            let tr = document.createElement('tr')
            tr.className = 'row row-param'
            tr.id = 'tp' + tp.id
            tr.setAttribute('onclick', 'select_tp(this)')
            $('#table_body_tech_processes').append(tr)
            let td_id = document.createElement('td')
            td_id.className = 'col-1 text-right'
            td_id.innerText = tp.id
            tr.appendChild(td_id)
            let td_name = document.createElement('td')
            td_name.className = 'col-3'
            tr.appendChild(td_name)
            let i_name = document.createElement('input')
            i_name.className = 'form-control'
            i_name.id = 'i_tp_name' + tp.id
            i_name.value = tp.name
            td_name.appendChild(i_name)
            // Стадии техпроцессов
            let td_stages = document.createElement('td')
            td_stages.className = 'col'
            tr.appendChild(td_stages)
            let ta_stages = document.createElement('textarea')
            ta_stages.className = 'form-control'
            ta_stages.style = 'height-min: 50px'
            ta_stages.id = 'ta_tp_stages' + tp.id
            let stages = tp.params.find((el) => el.name === 'stages')
            ta_stages.value = stages.value.join('\n')
            td_stages.appendChild(ta_stages)
            // ЛинкМап
            let lm = tp.params.find((el) => el.name === 'link_map')
            if (lm){
                let td_lm = document.createElement('td')
                td_lm.className = 'col'
                tr.appendChild(td_lm)
                let ta_lm = document.createElement('textarea')
                ta_lm.className = 'form-control'
                ta_lm.style = 'height-min: 50px'
                ta_lm.id = 'ta_lm' + tp.id
                ta_lm.value = (lm.value) ? lm.value.join('\n') : null
                td_lm.appendChild(ta_lm)
            }
            // Контрольное поле
            let td_c_f = document.createElement('td')
            td_c_f.className = 'col-2'
            tr.appendChild(td_c_f)
            let i_c_f = document.createElement('input')
            i_c_f.type = 'number'
            i_c_f.className = 'form-control'
            i_c_f.id = 'i_tp_cf' + tp.id
            let ctrl_field = tp.params.find((el) => el.name === 'control_field')
            i_c_f.value = ctrl_field.value
            td_c_f.appendChild(i_c_f)
        })
    }
}

function show_class_val() {
    clearTimeout(typingTimer);
    typingTimer = setTimeout(() =>{
        $('#s_link_val').text('')
        $.ajax({url:'gc4lp',
            method:'get',
            dataType:'json',
            data: {class_type: $('input[name="chb_link_type"]:checked').val(), class_val: $('#i_link_val').val()},
            success:function(data){
                let datalist = $('#dl_link_val')
                datalist.html('')
                // заполним классами даталист
                for (let i = 0; i < data.length; i++){
                    let op = document.createElement('option')
                    op.value = data[i].id
                    op.innerText = data[i].name
                    datalist.append(op)
                }
                // выведем подпись класса
                $('#i_link_def').val('')  // очистим поле объектов
                $('#dl_link_def').html('')  // очистим даталист объектов
                $('#s_link_def').text('')  // очистим подпись умолчания
                let s_link_val = $('#s_link_val')
                s_link_val.text('')
                let dl_link_val = $('#dl_link_val').children().toArray()
                let link_val = $('#i_link_val').val()
                let link_is_correct = false
                for (let i = 0; i < dl_link_val.length; i++){
                    if (dl_link_val[i].value === link_val){
                        s_link_val.text(dl_link_val[i].innerText)
                        $('#i_link_def').val('')
                        $('#s_link_def').val('')
                        link_is_correct = true
                        break
                    }
                }
                $('#b_save_params_dict').attr('disabled', !link_is_correct)
            },
            error: () => {$('#i_link_val').val('Ошибка')}
        })
    }, 2000)
}

// object_def_id - айди инпута, содержащего код объекта по умолчанию.
// dict_dop - словарь с 4 параметрами для запуска функции dict_objs_promp
function click_objs_promp(object_def_id, dict_dop) {
    let code = $('#' + object_def_id).val()
    if (!$('#' + dict_dop.datalist_id).children().length && !code)
        dict_objs_promp(dict_dop.link_type, dict_dop.link_id, code, dict_dop.datalist_id, dict_dop.span_default_id)
}

function dict_objs_promp(link_type, link_id, code, datalist_id, span_default_id, time_delay=true){
    function do_this(){
        let datalist = $('#' + datalist_id)
        datalist.html('')
        $.ajax({url:'gon4d',
            method:'get',
            dataType:'json',
            data: {link_type: link_type, link_id: link_id, code: code},
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
                let s_def = $('#' + span_default_id)
                s_def.text('')
                let arr_dl = datalist.children().toArray()
                let obj_is_correct = false
                for (let i = 0; i < arr_dl.length; i++){
                    if (code === arr_dl[i].value){
                        s_def.text(arr_dl[i].innerText)
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
    if (time_delay){
        clearTimeout(typingTimer)
        typingTimer = setTimeout(do_this, 3000)
    }
    else do_this()
}

// Подготовка к запуску функции dict_objs_promp для нового параметра
function dop_prepare_new_req(){
    let link_type = $('input[name="chb_link_type"]:checked').val()
    let link_id = $('#i_link_val').val()
    let code = $('#i_link_def').val()
    dict_objs_promp(link_type, link_id, code, 'dl_link_def', 's_link_def')

}

// Подготовка к запуску функции "клик по инпуту дефолт"
function cop_new_req() {
    let dict_dop = {}
    dict_dop.link_type = $('input[name="chb_link_type"]:checked').val()
    dict_dop.link_id = $('#i_link_val').val()
    dict_dop.datalist_id = 'dl_link_def'
    dict_dop.span_default_id = 's_link_def'
    click_objs_promp('i_link_def', dict_dop)
}

// Добавление оператора icontains - ищущего регистронезависимое вхождение текста в тег
jQuery.expr[":"].icontains = jQuery.expr.createPseudo(function (arg) {
    return function (elem) {
        return jQuery(elem).text().toLowerCase().indexOf(arg.toLowerCase()) >= 0;
    };
});

function full_search_in_tree(){
    let search_q = $('#i_search').val()
    let field_id = parseInt(search_q)
    if (search_q){
        $('#div_tree').attr('class', 'tag-invis')
        let div_search_result = $('#div_search_result')
        div_search_result.removeClass('tag-invis').html('')
        let base_url = get_path_from_url()
        function show_result(find){
            let el = JSON.parse(find.text())
            let url = base_url + '?i_id=' + el.id
            if (base_url === 'manage-class-tree'){
                if (el.formula === 'dict')
                    url += '&is_dict='
            }
            else{
                url += '&location='
                switch (el.formula) {
                    case 'dict':
                        url += 'd'
                        break
                    case 'tp':
                        url += 't'
                        break
                    default:
                        url += 'c'
                        break
                }
            }
            let li = document.createElement('li')
            let img
            switch(el.formula){
                case 'folder':
                    img = 'folder_closed_50'
                    break
                case 'tree':
                    img = 'tree_32_blue'
                    break
                case 'table':
                    img = 'book_50'
                    break
                case 'contract':
                    img = 'pen_50'
                    break
                case 'alias':
                    img = 'home_50'
                    break
                case 'array':
                    img = 'array_50'
                    break
                case 'dict':
                    img = 'star_50'
                    break
                case 'tp':
                    img = 'tp_50'
                    break
            }
            img = '<img src="/static/img/pics/' + img + '.png" width=20px>'
            li.innerHTML = '<a href="' + url + '">' + img + '&nbsp;' + el.name + '&nbsp;<b>ID:</b>' + el.id + '</a>'
            div_search_result.append(li)
        }
        if (isNaN(field_id)){
            // Поиск по имени
            let lis = $('li:icontains("' + search_q.toLowerCase() + '")').toArray()
            lis.forEach((el)=>show_result($('#' + el.id.replace('unit', 's_info'))))
        }
        else {
            // поиск по ID
            let find = $('#s_info' + field_id)
            if (find.length)
                show_result(find)
            find = $('#s_info_dict' + field_id)
            if (find.length)
                show_result(find)
            find = $('#s_info_tp' + field_id)
            if (find.length)
                show_result(find)
        }
    }
    else{
        $('#div_tree').removeClass('tag-invis')
        $('#div_search_result').addClass('tag-invis')
    }

}

function set_delay_settings(this_chb, is_contract=false){
    let id = this_chb.id.slice(5)
    if (this_chb.checked){
        let field
        if (id === 'new'){
            if (is_contract)
                field = {'delay': {'delay': true, 'handler': ''}}
            else
                field = {'delay_settings': {'auto_approve': false, 'handler': ''}}
        }
        else{
            field = JSON.parse($('#fields').text()).find(el => el.id === id * 1)
            if (is_contract){
                if (!field.delay)
                    field.delay = {'delay': false, 'handler': null}
            }
        }
        let tr = document.createElement('tr')
        tr.className = 'row'
        tr.id = 'tr_delay_settings_' + id
        let my_tr = this_chb.parentNode.parentNode
        my_tr.after(tr)
        let td_header = document.createElement('td')
        td_header.className = 'col-4'
        td_header.innerHTML = '<h5 class="text-center">Настройки планирования значений</h5>'
        tr.appendChild(td_header)

        let td_type = document.createElement('td')
        td_type.className = 'col text-center'
        tr.appendChild(td_type)
        td_type.innerHTML = '<div class="row"><div class="col">Тип ответственного</div><div class="col text-left">' +
            '<input type="radio" id="r_user_' + id + '" name="r_handler_type_' + id + '"> <label for="r_user_' + id +
            '" class="font-weight-normal">Пользователь</label><br>' +
            '<input type="radio" id="r_eval_' + id + '" name="r_handler_type_' + id + '"> <label for="r_eval_' + id +
            '" class="font-weight-normal">Формула</label></div></div>'
        let handler = (is_contract) ? field.delay.handler : field.delay_settings.handler
        if (typeof handler === 'string')
            $('#r_eval_' + id).attr('checked', true)
        else
            $('#r_user_' + id).attr('checked', true)

        // ответственный
        tr.appendChild(fill_delay_handler(id, handler))
    }
    else{
        $('#tr_delay_settings_' + id).remove()
    }
}

function set_totals_settings(this_chb, is_contract=false){
    let id = this_chb.id.slice(7)
    if (this_chb.checked){
        let field = (id === 'new') ? null: JSON.parse($('#fields').text()).find(el => el.id === id * 1)
        let data_type = (field) ? field.formula : $('#s_type').val()
        if (data_type !== 'float')
            return false
        let tr = document.createElement('tr')
        tr.className = 'row'
        tr.id = 'tr_totals_settings_' + id
        let my_tr = this_chb.parentNode.parentNode
        my_tr.after(tr)
        let td_header = document.createElement('td')
        td_header.className = 'col-4'
        td_header.innerHTML = '<h5 class="text-center">Настройки итогов</h5>'
        tr.appendChild(td_header)

        let td_val = document.createElement('td')
        td_val.className = 'col text-center'
        tr.appendChild(td_val)
        let settings = {'totals': []}
        if (field && field.settings && 'totals' in field.settings)
            settings = field.settings
        let dict_totals = {'sum': 'сумма', 'avg': 'среднее', 'min': 'минимум', 'max': 'максимум', 'count': 'количетсво'}
        // Выведем существующие итоги
        for (let i = 0; i < settings.totals.length; i++){
            let span_tot = document.createElement('span')
            span_tot.className = 'btn btn-outline-secondary'
            span_tot.id = 'total_' + id + '_' + settings.totals[i]
            span_tot.innerText = dict_totals[settings.totals[i]]
            span_tot.setAttribute('onclick', 'art(this, false)')
            td_val.appendChild(span_tot)
        }
        let button_add = document.createElement('button')
        button_add.className = 'btn btn-outline-primary'
        button_add.innerText = '+'
        button_add.id = 'b_totals_' + id
        button_add.setAttribute('data-toggle', "dropdown")
        button_add.setAttribute('aria-haspopup', "true")
        button_add.setAttribute('aria-expanded', "false")
        // выпадающий список итогов
        let ddd = document.createElement('div')
        ddd.className = 'dropdown d-inline'
        td_val.appendChild(ddd)
        ddd.appendChild(button_add)
        let div_ddm = document.createElement('div')
        div_ddm.className = 'dropdown-menu'
        div_ddm.setAttribute('aria-labelledby', 'dropdownMenuButton')
        ddd.appendChild(div_ddm)
        for (let dt in dict_totals){
            if (settings.totals.includes(dt))
                continue
            let di = document.createElement('span')
            di.className = 'dropdown-item'
            di.id = 's_total_' + id + '_' + dt
            di.innerText = dict_totals[dt]
            di.setAttribute('onclick', 'art(this)')
            div_ddm.appendChild(di)
        }
    }
    else{
        $('#tr_totals_settings_' + id).remove()
    }
}

// art = add / remove total
function art(this_span, is_add=true){

    let str_prefix, class_name, other_prefix, str_func
    if (is_add){
        str_prefix = 's_total_'
        other_prefix = 'total_'
        class_name = 'btn btn-outline-secondary'
        str_func = 'art(this, false)'
    }
    else{
        str_prefix = 'total_'
        other_prefix = 's_total_'
        class_name = 'dropdown-item'
        str_func = 'art(this)'
    }
    let re = new RegExp(str_prefix + '([\\dnew]+)_(\\w+)')
    let data = this_span.id.match(re)
    let req_id = data[1]
    let total_name = data[2]
    let dict_totals = {'sum': 'сумма', 'avg': 'среднее', 'min': 'минимум', 'max': 'максимум', 'count': 'количетсво'}
    let new_total = document.createElement('span')
    new_total.className = class_name
    new_total.id = other_prefix + req_id + '_' + total_name
    new_total.innerText = dict_totals[total_name]
    new_total.setAttribute('onclick', str_func)
    if (is_add)
        this_span.parentNode.parentNode.parentNode.insertBefore(new_total, this_span.parentNode.parentNode)
    else
        $('#b_totals_' + req_id)[0].nextSibling.appendChild(new_total)
    this_span.remove()
}

$(document).on('change', 'input[name^="r_handler_type_"]', function(){
    let parent_tr = this.parentNode.parentNode.parentNode.parentNode
    let id = parent_tr.id.slice(18)
    $('#td_handler_' + id).remove()
    let handler = (this.id[2] === 'u') ? 0 : ''
    let td_handler = fill_delay_handler(id, handler)
    parent_tr.appendChild(td_handler)
})

function fill_delay_handler(id, handler){
    let td_handler = document.createElement('td')
    td_handler.className = 'col-4'
    td_handler.id = 'td_handler_' + id
    if (typeof handler === 'string'){
        let eval_tag = document.createElement('textarea')
        eval_tag.id = 'ta_handler_' + id
        eval_tag.className = 'form-control'
        eval_tag.style = 'min-height: 80px'
        eval_tag.innerText = handler
        td_handler.appendChild(eval_tag)
        ta_to_editor(eval_tag)
    }
    else{
        let dl = document.createElement('datalist')
        dl.id = 'dl_handler_' + id
        td_handler.appendChild(dl)
        let label_handler = document.createElement('span')
        label_handler.innerText = 'Ответственный'
        td_handler.appendChild(label_handler)
        let inp_handler = document.createElement('input')
        inp_handler.className = 'form-control'
        inp_handler.style = 'display: inline; width: auto'
        inp_handler.id = 'i_handler_' + id
        inp_handler.value = handler
        inp_handler.setAttribute('list', 'dl_handler_' + id)
        inp_handler.setAttribute('oninput', 'get_users(this, $("#dl_handler_"' + id + '))')
        td_handler.appendChild(inp_handler)
        get_users(inp_handler, $('#dl_handler_' + id))
    }
    return td_handler
}

