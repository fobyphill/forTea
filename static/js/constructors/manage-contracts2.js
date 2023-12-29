function new_tp(this_button) {
    this_button.setAttribute('disabled', true)
    let tr = document.createElement('tr')
    tr.className = 'row row-param'
    tr.setAttribute('onclick', 'select_tp(this, true)')
    $('#table_body_tech_processes').append(tr)
    // Название
    let td_name = document.createElement('td')
    td_name.className = 'col-3'
    let input_name = document.createElement('input')
    input_name.className = 'form-control'
    input_name.id = 'i_new_tp_name'
    td_name.appendChild(input_name)
    tr.appendChild(td_name)
    // Стадии
    let td_stages = document.createElement('td')
    td_stages.className = 'col'
    let ta_stages = document.createElement('textarea')
    ta_stages.className = 'form-control'
    ta_stages.style = 'min-height: 50px;'
    ta_stages.value = 'Создан'
    ta_stages.id = 'ta_new_tp_stages'
    td_stages.appendChild(ta_stages)
    tr.appendChild(td_stages)
    // Линкмап
    let td_lm = document.createElement('td')
    td_lm.className = 'col'
    let ta_lm = document.createElement('textarea')
    ta_lm.className = 'form-control'
    ta_lm.style = 'min-height: 50px;'
    ta_lm.value = ''
    ta_lm.id = 'ta_new_tp_lm'
    td_lm.appendChild(ta_lm)
    tr.appendChild(td_lm)
    // Контрольное поле
    let td_control_field = document.createElement('td')
    td_control_field.className = 'col-2'
    let i_c_f = document.createElement('input')
    i_c_f.className = 'form-control'
    i_c_f.id = 'i_new_tp_control_field'
    td_control_field.appendChild(i_c_f)
    tr.appendChild(td_control_field)
}

function save_all_tps(){
    let output_json = {}
    // Определим, был ли создан новый техпроцесс
    let new_name = $('#i_new_tp_name')
    if (new_name.length){
        let new_tp = {}
        new_tp.name = new_name.val()
        new_tp.stages = $('#ta_new_tp_stages').val()
        new_tp.control_field = $('#i_new_tp_control_field').val()
        new_tp.lm = $('#ta_new_tp_lm').val()
        output_json.new_tp = new_tp
    }
    // Соберем данные существующих техпроцессов
    let tps = JSON.parse($('#system_fields').text())
    tps.forEach((tp) =>{
        tp.name = $('#i_tp_name' + tp.id).val()
        tp.params.forEach((p) =>{
            if (p.name === 'stages')
                p.value = $('#ta_tp_stages' + tp.id).val().split('\n')
            else if (p.name === 'control_field')
                p.value = parseInt($('#i_tp_cf' + tp.id).val())
            else if (p.name === 'link_map')
                p.value = $('#ta_lm' + tp.id).val()
        })
    })
    output_json.current_tps = tps
    // Отправим форму
    send_form_with_param('tps', JSON.stringify(output_json))
}

function select_tp(this_tr, is_new=false){
    if (is_new)
        $("#b_del_tp").attr("disabled", true)
    else
        $("#b_del_tp").attr("disabled", false)
    select_param(this_tr)
}

function delete_tp() {
    let active_row = $('.row-param.table-active')
    if (active_row.length){
        let id = active_row[0].id
        if (id && id.slice(0, 2) === 'tp')
            send_form_with_param('delete_tp', id.slice(2))
    }
}

// ancsotp = add new child stage of techprocess
function ancsotp(stage_id) {
    let div_children = $('#div_children_' + stage_id)
    let children = div_children.children()
    let exist_children = []
    exist_children.push(parseInt(stage_id))
    for (let i = 0; i < children.length; i++)
        exist_children.push(parseInt(children[i].children[0].innerText))
    let stages = JSON.parse($('#fields').text())
    let new_stages = []
    for (let i = 0; i < stages.length; i++){
        if (!exist_children.includes(stages[i].id))
            new_stages.push({'id': stages[i].id, 'name': stages[i].name})
    }
    if (new_stages.length){
        let child_list = document.createElement('select')
        child_list.className = 'form-control'
        child_list.setAttribute('onchange', 'sechist(this)')
        let op = document.createElement('option')
        op.value = '0'
        op.innerText = 'Выберите дочернюю стадию'
        child_list.appendChild(op)
        for (let i = 0; i < new_stages.length; i++){
            let op = document.createElement('option')
            op.value = new_stages[i].id
            op.innerText = new_stages[i].name
            child_list.appendChild(op)
        }
        div_children.append(child_list)
    }
    $('#b_new_child_' + stage_id).parent().parent().attr('class', 'tag-invis')
}

function save_stages() {
    let array_stages = []
    $('#tp_body_stages').children().each(function () {
        let children = []
        $('#div_children_' + this.id).children().each(function() {
            if (this.children[0].nodeName === 'DIV')
                children.push(this.children[0].innerText)
            else if (this.nodeName === 'SELECT' && this.value !== '0')
                children.push(this.value)
        })
        let stage = {'id': this.id, 'name': $('#i_stage_name_' + this.id).val(),
            'handler': $('#i_stage_handler_' + this.id).val(), 'children': children}
        array_stages.push(stage)
    })
    result = JSON.stringify(array_stages)
    send_form_with_param('save_tp', result)
}

function new_stage(){
    let tr = document.createElement('tr')
    tr.className = 'row row-param'
    tr.id = 'new'
    let onclick_fun = 'select_param(this, {\'is_stage\': true})'
    tr.setAttribute('onclick', onclick_fun)
    $('#tp_body_stages').append(tr)
    let td_name = document.createElement('td')
    td_name.className = 'col-3'
    tr.appendChild(td_name)
    let i_name = document.createElement('input')
    i_name.className = 'form-control'
    i_name.id = 'i_stage_name_new'
    td_name.appendChild(i_name)
    let td_handler = document.createElement('td')
    td_handler.className = 'col'
    tr.appendChild(td_handler)
    let i_handler = document.createElement('input')
    i_handler.id = 'i_stage_handler_new'
    i_handler.className = 'form-control'
    i_handler.style = 'width: 4rem; display: inline'
    let oninput = "get_users(this, $('#dl_stage_handler_info_new')), get_user_by_id(this.value, $('#s_stage_handler_info_new'))"
    i_handler.setAttribute('oninput', oninput)
    i_handler.setAttribute('list', 'dl_stage_handler_info_new')
    td_handler.appendChild(i_handler)
    let dl = document.createElement('datalist')
    dl.id = 'dl_stage_handler_info_new'
    td_handler.appendChild(dl)
    let s_handler_info = document.createElement('span')
    s_handler_info.id = 's_stage_handler_info_new'
    td_handler.appendChild(s_handler_info)
    let td_children = document.createElement('td')
    td_children.className = 'col'
    tr.appendChild(td_children)
    let div_children = document.createElement('div')
    div_children.id = 'div_children_new'
    td_children.appendChild(div_children)
    let div_row_button = document.createElement('div')
    div_row_button.className = 'row'
    td_children.appendChild(div_row_button)
    let div_col = document.createElement('div')
    div_col.className = 'col-3 ml-auto'
    div_row_button.appendChild(div_col)
    let b_add = document.createElement('button')
    b_add.className = 'btn btn-outline-primary mx-4'
    b_add.id = 'b_new_child_new'
    b_add.setAttribute('onclick', 'ancsotp(this.id.slice(12))')
    b_add.innerText = '+'
    div_col.appendChild(b_add)
    $('#b_new_stage').attr('disabled', true)
    tr.click()
}

function delete_stage() {
    let del_stage = $('tr.table-active')
    if (del_stage.length)
        send_form_with_param('delete_stage', del_stage[0].id)
}

function select_class_type() {
    if ($('#s_folder_class').val() === 'tp'){
        let control_field = $('#s_control_field')
        control_field.html('')
        control_field.attr('class', 'form-control')
        let op = document.createElement('option')
        op.value = '0'
        op.innerText = 'Выберите контрольное поле'
        control_field.append(op)
        let class_id = $('#i_parent').val()
        try{class_id = parseInt(class_id)}
        catch{
            return false
        }
        gaff(class_id, control_field)
    }
    else $('#s_control_field').attr('class', 'tag-invis')
}

function init_input_user(this_input) {
    if (this_input.defaultValue)
        return false
    let val = this_input.value
    this_input.defaultValue = true
    this_input.value = val
    let output_data = $('#dl_stage_handler_info_' + this_input.id.slice(16))
    get_users(this_input, output_data)
}

