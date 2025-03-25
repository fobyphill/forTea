var my_linkmap

// acilm = add contract in linkMap
function acilm(link_map, is_task=false){
    let b_add_class = $('#b_acilm')[0]
    if (typeof link_map === 'string' && link_map === 'new'){
        link_map = [{'class_id': 'new', 'code': '', 'method': 'e', 'event_kind': [], 'params': []}]
        if (is_task){
            link_map[0].loc = 't'
            link_map[0].event_kind.push('u')
        }
    }
    if (!link_map)
        return false
    let ld_methods = [ {'id': 'e', 'name': 'Редактирование'}, {'id': 'n', 'name': 'Создание'},
        {'id': 'en', 'name': 'Редактирование или новый'},
        {'id': 'wo', 'name': 'Списание'}, {'id': 'pe', 'name': 'Пакетное редактирование'} ]
    for (let i = link_map.length - 1; i >= 0; i--) {
        let contract_number = (link_map[i].class_id === 'new') ? 'new' : i
        let div_contract = document.createElement('div')
        div_contract.id = 'div_lm_contract_' + contract_number
        b_add_class.after(div_contract)
        if (contract_number === 'new')
            b_add_class.remove()
        let hr = document.createElement('hr')
        hr.className = 'border border-secondary'
        div_contract.appendChild(hr)
        let input_group_id = document.createElement('div')
        input_group_id.className = 'input-group mb-1'
        div_contract.appendChild(input_group_id)
        if (is_task) {
            let div_radio = document.createElement('div')
            div_radio.className = "btn-group btn-group-toggle"
            div_radio.setAttribute('data-toggle', 'buttons')
            input_group_id.appendChild(div_radio)
            // Справочники
            let l_hbs = document.createElement('label')
            l_hbs.className = "btn btn-outline-secondary"
            if (link_map[i].loc === 't')
                l_hbs.className += ' active'
            div_radio.appendChild(l_hbs)
            let r_hbs = document.createElement('input')
            r_hbs.type = 'radio'
            r_hbs.name = 'r_datatype_' + contract_number
            r_hbs.id = 'r_datatype_table_' + contract_number
            r_hbs.checked = (link_map[i].loc === 't')
            l_hbs.appendChild(r_hbs)
            l_hbs.appendChild(document.createTextNode('Справочники'))
            // Контракты
            let l_cs = document.createElement('label')
            l_cs.className = "btn btn-outline-secondary"
            if (link_map[i].loc === 'c')
                l_cs.className += ' active'
            div_radio.appendChild(l_cs)
            let r_cs = document.createElement('input')
            r_cs.type = 'radio'
            r_cs.name = 'r_datatype_' + contract_number
            r_cs.id = 'r_datatype_contract_' + contract_number
            r_cs.checked = (link_map[i].loc === 'c')
            l_cs.appendChild(r_cs)
            l_cs.appendChild(document.createTextNode('Контракты'))
        }
        let span_contract_id = document.createElement('span')
        span_contract_id.className = 'input-group-text border-0 bg-transparent text-left'
        span_contract_id.innerText = 'ID'
        if (!is_task)
            span_contract_id.innerText += ' контракта'
        input_group_id.appendChild(span_contract_id)
        if (contract_number === 'new') {
            let input_contract_id = document.createElement('input')
            input_contract_id.className = 'form-control'
            input_contract_id.id = 'i_contract_id_new'
            input_contract_id.type = 'number'
            input_group_id.appendChild(input_contract_id)
        } else {
            let show_contract_id = document.createElement('span')
            show_contract_id.className = 'form-control'
            show_contract_id.id = 'show_contract_id_' + i
            show_contract_id.innerText = link_map[i].class_id
            input_group_id.appendChild(show_contract_id)
        }
        let but_del = document.createElement('button')
        but_del.type = 'button'
        but_del.className = 'btn border-0 btn-outline-danger'
        but_del.innerText = 'X'
        but_del.setAttribute('onclick', 'this.parentNode.parentNode.remove()')
        input_group_id.appendChild(but_del)

        if (link_map[i].method !== 'n'){
            // Код
            let input_group_code = document.createElement('div')
            input_group_code.className = 'input-group mb-1'
            div_contract.appendChild(input_group_code)
            let span_code = document.createElement('span')
            span_code.className = 'input-group-text border-0 bg-transparent text-left'
            span_code.innerText = 'Код'
            input_group_code.appendChild(span_code)
            let ta_code = document.createElement('textarea')
            ta_code.className = 'form-control'
            ta_code.style['min-height'] = '0.5rem'
            ta_code.id = 'ta_code' + contract_number
            ta_code.value = link_map[i].code
            if (link_map[i].method === 'n')
                ta_code.setAttribute('readonly', true)
            input_group_code.appendChild(ta_code)
        }
        // Метод триггера
        let div_method = document.createElement('div')
        div_method.className = 'input-group mb-1'
        div_contract.appendChild(div_method)
        let span_method = document.createElement('span')
        span_method.className = 'input-group-text border-0 bg-transparent text-left'
        span_method.innerText = 'Метод триггера'
        div_method.appendChild(span_method)
        if (link_map[i].class_id === 'new'){
            let select_method = document.createElement('select')
            select_method.className = 'form-control'
            select_method.id = 's_method_' + contract_number
            select_method.setAttribute('onchange', 'cwo(this)')
            ld_methods.forEach((el) =>{
                let opt = document.createElement('option')
                opt.value = el.id
                opt.innerText = el.name
                select_method.appendChild(opt)
            })
            div_method.appendChild(select_method)
        }
        else {
            span_method.innerHTML += ': &nbsp;<b>' + ld_methods.find(el => el.id === link_map[i].method).name + '</b>'
            let s_method = document.createElement('input')
            s_method.type = 'hidden'
            s_method.id = 's_method_' + contract_number
            s_method.value = link_map[i].method
            div_method.appendChild(s_method)
        }
        // вид события
        let input_group_event_kind = document.createElement('div')
        input_group_event_kind.className = 'input-group mb-1'
        div_contract.appendChild(input_group_event_kind)
        if (!is_task) {
            let span_event_kind = document.createElement('span')
            span_event_kind.className = 'input-group-text border-0 bg-transparent'
            span_event_kind.innerText = "Вид события"
            input_group_event_kind.appendChild(span_event_kind)
            let html_chbs = '<span class="my-auto ml-3">Создан</span>' +
                '<input type="checkbox" id="chb_event_' + contract_number + '_make" value="m">' +
                '<span class="my-auto ml-3">Обновлен</span><input type="checkbox" id="chb_event_' +
                contract_number + '_update" value="u">' +
                '<span class="my-auto ml-3">Удален</span><input type="checkbox" id="chb_event_' +
                contract_number + '_remove" value="r">' +
                '<span class="my-auto ml-3">Отложен</span><input type="checkbox" id="chb_event_' +
                contract_number + '_delay" value="d">'
            input_group_event_kind.innerHTML += html_chbs
            let dict_events = {'m': 'make', 'u': 'update', 'r': 'remove', 'd': 'delay'}
            link_map[i].event_kind.forEach(el => $('#chb_event_' + contract_number + '_' + dict_events[el]).attr('checked', true))
        }
        // параметры редактирования объекта
        let div_edit_table = document.createElement('div')
        div_edit_table.id = 'div_edit_table_' + contract_number
        div_contract.appendChild(div_edit_table)
        // параметры создания объекта
        let div_create_table = document.createElement('div')
        div_create_table.id = 'div_create_table_' + contract_number
        div_contract.appendChild(div_create_table)

        erandrat(contract_number, link_map[i].method)

        // заполним таблицу редактирования
        if (['e', 'en', 'wo', 'pe'].includes(link_map[i].method)){
            let params_table = $('#table_lm_params' + contract_number)[0]
            dpolc(link_map[i].params, params_table, link_map[i].method)
        }
        // заполним таблицу создания
        if (['n', 'en'].includes(link_map[i].method)){
            let params_create_table = $('#table_lm_params_create' + contract_number)[0]
            dpolc(link_map[i].create_params, params_create_table, link_map[i].method, true)
        }
    }
}


// acilot = add contract in LM of TP
function acilot(this_button){
    let div_lm = document.createElement('div')
    div_lm.id = 'div_lm_new'
    this_button.parentNode.insertBefore(div_lm, this_button)
    this_button.remove()
// ID contract
    let hr = document.createElement('hr')
    div_lm.appendChild(hr)
    let div_id = document.createElement('div')
    div_id.className = 'input-group mb-1'
    div_lm.appendChild(div_id)
    let span_id = document.createElement('span')
    span_id.className = 'input-group-text'
    span_id.innerText = 'ID контракта'
    div_id.appendChild(span_id)
    let input_id = document.createElement('input')
    input_id.className = 'form-control p-0'
    input_id.id = 'i_tp_lm_contract_id_new'
    input_id.type = 'number'
    div_id.appendChild(input_id)
    let button_del = document.createElement('button')
    button_del.className = 'btn btn-outline-danger'
    button_del.innerText = 'Удалить'
    button_del.setAttribute('onclick', 'this.parentNode.parentNode.remove()')
    div_id.appendChild(button_del)
// Code
    let div_code = document.createElement('div')
    div_code.className = 'input-group mb-1'
    div_lm.appendChild(div_code)
    let span_code = document.createElement('span')
    span_code.className = 'input-group-text'
    span_code.innerText = 'Код'
    div_code.appendChild(span_code)
    let ta_code = document.createElement('textarea')
    ta_code.className = 'form-control'
    ta_code.style['min-height'] = '2rem'
    ta_code.id = 'ta_code_new'
    div_code.appendChild(ta_code)
// Стадии
    let div_stages = document.createElement('div')
    div_stages.className = 'input-group mb-1'
    div_lm.appendChild(div_stages)
    let span_stages = document.createElement('span')
    span_stages.className = 'input-group-text'
    span_stages.innerText = 'Стадии'
    div_stages.appendChild(span_stages)
    let select_stage = document.createElement('select')
    select_stage.className = 'form-control'
    select_stage.setAttribute('multiple', true)
    select_stage.id = 'select_lm_stages_new'
    let fields = JSON.parse($('#fields').html())
    select_stage.setAttribute('size', fields.length)
    for (let i = 0; i < fields.length; i++){
        let op = document.createElement('option')
        op.value = fields[i].id
        op.innerText = fields[i].name
        select_stage.appendChild(op)
    }
    div_stages.appendChild(select_stage)
// метод триггера
    let div_method = document.createElement('div')
    div_method.className = 'input-group mb-1'
    div_lm.appendChild(div_method)
    let span_method = document.createElement('span')
    span_method.className = 'input-group-text'
    span_method.innerText = 'Метод триггера'
    div_method.appendChild(span_method)
    let select_method = document.createElement('select')
    select_method.className = 'form-control'
    select_method.id = 's_method_new'
    select_method.setAttribute('onclick', 'cwo(this)')
    select_method.innerHTML = '<option value="n">Создание</option><option value="e">Редактирование</option>' +
        '<option value="en">Редактирование или создание</option><option value="wo">Списание</option>' +
        '<option value="pe">Пакетное редактирование</option>'
    div_method.appendChild(select_method)
// Действия
    let div_acts = document.createElement('div')
    div_acts.className = 'input-group mb-1'
    div_lm.appendChild(div_acts)
    let span_acts = document.createElement('span')
    span_acts.className = 'input-group-text'
    span_acts.innerText = 'Действия'
    div_acts.appendChild(span_acts)
    let label_delay = document.createElement('label')
    label_delay.className = 'form-control'
    label_delay.innerHTML = 'Delay<input type="checkbox" id="chb_tp_lm_delay_new">'
    div_acts.appendChild(label_delay)
    let label_update = document.createElement('label')
    label_update.className = 'form-control'
    label_update.innerHTML = 'Update<input type="checkbox" id="chb_tp_lm_update_new">'
    div_acts.appendChild(label_update)
// Параметры редактирования объекта
    let div_edit = document.createElement('div')
    div_edit.id = 'div_edit_table_new'
    div_lm.appendChild(div_edit)
    let div_create = document.createElement('div')
    div_create.id = 'div_create_table_new'
    div_lm.appendChild(div_create)
    erandrat('new', 'n')
}

// Удалить после 20.01.2025
// function acilm_old(link_map, is_task=false){
//     let b_add_class = $('#b_acilm')[0]
//     if (typeof link_map === 'string' && link_map === 'new'){
//         link_map = [{'class_id': 'new', 'code': '', 'new_code': false, 'writeoff': false, 'event_kind': [], 'params': []}]
//         if (is_task){
//             link_map[0].loc = 't'
//             link_map[0].event_kind.push('u')
//         }
//     }
//     if (!link_map)
//         return false
//     for (let i = link_map.length - 1; i >= 0; i--) {
//         let contract_number = (link_map[i].class_id === 'new') ? 'new' : i
//         let div_contract = document.createElement('div')
//         div_contract.id = 'div_lm_contract_' + contract_number
//         b_add_class.after(div_contract)
//         if (contract_number === 'new')
//             b_add_class.remove()
//         let hr = document.createElement('hr')
//         hr.className = 'border border-secondary'
//         div_contract.appendChild(hr)
//         let input_group_id = document.createElement('div')
//         input_group_id.className = 'input-group mb-1'
//         div_contract.appendChild(input_group_id)
//         if (is_task) {
//             let div_radio = document.createElement('div')
//             div_radio.className = "btn-group btn-group-toggle"
//             div_radio.setAttribute('data-toggle', 'buttons')
//             input_group_id.appendChild(div_radio)
//             // Справочники
//             let l_hbs = document.createElement('label')
//             l_hbs.className = "btn btn-outline-secondary"
//             if (link_map[i].loc === 't')
//                 l_hbs.className += ' active'
//             div_radio.appendChild(l_hbs)
//             let r_hbs = document.createElement('input')
//             r_hbs.type = 'radio'
//             r_hbs.name = 'r_datatype_' + contract_number
//             r_hbs.id = 'r_datatype_table_' + contract_number
//             r_hbs.checked = (link_map[i].loc === 't')
//             l_hbs.appendChild(r_hbs)
//             l_hbs.appendChild(document.createTextNode('Справочники'))
//             // Контракты
//             let l_cs = document.createElement('label')
//             l_cs.className = "btn btn-outline-secondary"
//             if (link_map[i].loc === 'c')
//                 l_cs.className += ' active'
//             div_radio.appendChild(l_cs)
//             let r_cs = document.createElement('input')
//             r_cs.type = 'radio'
//             r_cs.name = 'r_datatype_' + contract_number
//             r_cs.id = 'r_datatype_contract_' + contract_number
//             r_cs.checked = (link_map[i].loc === 'c')
//             l_cs.appendChild(r_cs)
//             l_cs.appendChild(document.createTextNode('Контракты'))
//         }
//         let span_contract_id = document.createElement('span')
//         span_contract_id.className = 'input-group-text border-0 bg-transparent text-left'
//         span_contract_id.innerText = 'ID'
//         if (!is_task)
//             span_contract_id.innerText += ' контракта'
//         input_group_id.appendChild(span_contract_id)
//         if (contract_number === 'new') {
//             let input_contract_id = document.createElement('input')
//             input_contract_id.className = 'form-control'
//             input_contract_id.id = 'i_contract_id_new'
//             input_contract_id.type = 'number'
//             input_group_id.appendChild(input_contract_id)
//         } else {
//             let show_contract_id = document.createElement('span')
//             show_contract_id.className = 'form-control'
//             show_contract_id.id = 'show_contract_id_' + i
//             show_contract_id.innerText = link_map[i].class_id
//             input_group_id.appendChild(show_contract_id)
//         }
//         let but_del = document.createElement('button')
//         but_del.type = 'button'
//         but_del.className = 'btn border-0 btn-outline-danger'
//         but_del.innerText = 'X'
//         but_del.setAttribute('onclick', 'this.parentNode.parentNode.remove()')
//         input_group_id.appendChild(but_del)
//         // Код
//         let input_group_code = document.createElement('div')
//         input_group_code.className = 'input-group mb-1'
//         div_contract.appendChild(input_group_code)
//         let span_code = document.createElement('span')
//         span_code.className = 'input-group-text border-0 bg-transparent text-left'
//         span_code.innerText = 'Код'
//         input_group_code.appendChild(span_code)
//         let input_code = document.createElement('input')
//         input_code.className = 'form-control'
//         input_code.id = 'i_code' + contract_number
//         input_code.value = link_map[i].code
//         input_group_code.appendChild(input_code)
//         let span_or_new = document.createElement('span')
//         span_or_new.className = 'input-group-text border-0 bg-transparent text-left'
//         span_or_new.innerText = 'или новый'
//         input_group_code.appendChild(span_or_new)
//         let chb_or_new = document.createElement('input')
//         chb_or_new.type = 'checkbox'
//         chb_or_new.checked = link_map[i].new_code
//         chb_or_new.id = 'chb_or_new' + contract_number
//         let str_cn = (typeof contract_number === 'number') ? String(contract_number) : '\'' + contract_number + '\''
//         chb_or_new.setAttribute('onclick', 'tucrepa(this.checked, ' + str_cn + ')')
//         input_group_code.appendChild(chb_or_new)
//         // списание
//         let input_group_writeoff = document.createElement('div')
//         input_group_writeoff.className = 'input-group mb-1'
//         div_contract.appendChild(input_group_writeoff)
//         input_group_writeoff.innerHTML = '<span class="input-group-text border-0 bg-transparent text-left">Списание</span>'
//         let chb_wo = document.createElement('input')
//         chb_wo.type = 'checkbox'
//         chb_wo.checked = link_map[i].writeoff
//         chb_wo.id = 'chb_wo' + contract_number
//         chb_wo.setAttribute('onclick', 'cwo(this)')
//         input_group_writeoff.appendChild(chb_wo)
//         if (chb_wo.checked)
//             chb_or_new.disabled = true
//         // вид события
//         let input_group_event_kind = document.createElement('div')
//         input_group_event_kind.className = 'input-group mb-1'
//         div_contract.appendChild(input_group_event_kind)
//         if (!is_task) {
//             let span_event_kind = document.createElement('span')
//             span_event_kind.className = 'input-group-text border-0 bg-transparent'
//             span_event_kind.innerText = "Вид события"
//             input_group_event_kind.appendChild(span_event_kind)
//             let html_chbs = '<span class="my-auto ml-3">Создан</span>' +
//                 '<input type="checkbox" id="chb_event_' + contract_number + '_make" value="m">' +
//                 '<span class="my-auto ml-3">Обновлен</span><input type="checkbox" id="chb_event_' +
//                 contract_number + '_update" value="u">' +
//                 '<span class="my-auto ml-3">Удален</span><input type="checkbox" id="chb_event_' +
//                 contract_number + '_remove" value="r">' +
//                 '<span class="my-auto ml-3">Отложен</span><input type="checkbox" id="chb_event_' +
//                 contract_number + '_delay" value="d">'
//             input_group_event_kind.innerHTML += html_chbs
//             let dict_events = {'m': 'make', 'u': 'update', 'r': 'remove', 'd': 'delay'}
//             link_map[i].event_kind.forEach(el => $('#chb_event_' + contract_number + '_' + dict_events[el]).attr('checked', true))
//         }
//         // параметры редактирования объекта
//         let input_group_params = document.createElement('div')
//         input_group_params.className = 'input-group mb-1'
//         div_contract.appendChild(input_group_params)
//         input_group_params.innerHTML = '<span class="input-group-text border-0 bg-transparent text-left">Параметры редактирования объекта' +
//             '</span><button class=" btn btn-outline-info" id="b_add_lm_param' + contract_number + '" ' +
//             'onclick="apicilm(this)">+</button>'
//         let params = link_map[i].params
//         let params_table = document.createElement('table')
//         params_table.className = 'table table-bordered'
//         params_table.style['border'] = 'None'
//         params_table.id = 'table_lm_params' + contract_number
//         div_contract.appendChild(params_table)
//         let sign_or_limit = (link_map[i].writeoff) ? 'Лимит' : 'Знак'
//         let style_sign = (link_map[i].writeoff) ? 'col-2 text-center' : 'col-1 text-center'
//         let into_table = '<thead><tr class="row"><th class="col-1 text-right">ID</th>' +
//             '<th class="col text-center" >Значение</th>' +
//             '<th class="' + style_sign + '" style="white-space: nowrap;">' + sign_or_limit
//             + '</th><th class="col-1"></th></tr></thead><tbody></tbody>'
//         params_table.innerHTML = into_table
//         dpolc(params, params_table)
//         let div_create_params = document.createElement('div')
//         div_create_params.id = 'div_create_params_' + contract_number
//         div_contract.appendChild(div_create_params)
//         // параметры создания объекта
//         if (link_map[i].new_code)
//             tucrepa(true, contract_number)
//     }
// }


// apicilm = add param in contract in linkMap
function apicilm(this_button, method){
    let is_create = (Boolean(this_button.id.match(/b_add_lm_param_create/)))
    let slice_quant = (is_create) ? 21 : 14
    let contract_number = this_button.id.slice(slice_quant)
    let params = ['new']
    let table_name_begin = (is_create) ? '#table_lm_params_create' : '#table_lm_params'
    let table = $(table_name_begin + contract_number)[0]
    dpolc(params, table, method, is_create)
}

// apitilm = add param in TP in LM
function apitilm(this_button, lm_number, event_type, method){
    let table_id = '#table_tp_lm_param_' + event_type + lm_number
    let table_body = $(table_id).children().last()

    let tr = document.createElement('tr')
    tr.className = 'row'
    table_body.append(tr)

    let td_id = document.createElement('td')
    td_id.className = 'col-1 text-right px-0'
    tr.appendChild(td_id)

    let input_id = document.createElement('input')
    input_id.className = 'form-control p-0'
    input_id.id = 'i_tp_lm_' + event_type + 'id_' + lm_number
    input_id.type = 'number'
    td_id.appendChild(input_id)

    let td_val = document.createElement('td')
    td_val.className = 'col'
    tr.appendChild(td_val)

    let ta_val = document.createElement('textarea')
    ta_val.className = 'form-control'
    ta_val.id = 'ta_tp_lm_' + event_type + 'val_' + lm_number
    ta_val.style['min-height'] = '2rem'
    td_val.appendChild(ta_val)

    if (event_type === 'edit_'){
        let td_3 = document.createElement('td')
        td_3.className = (method === 'wo') ? 'col-2' : 'col-1'
        tr.appendChild(td_3)
        if (method === 'wo'){
            let input_limit = document.createElement('input')
            input_limit.className = 'form-control'
            input_limit.id = 'i_tp_lm_limit_edit_' + lm_number
            td_3.appendChild(input_limit)
        }
        else{
            let select_sign = document.createElement('select')
            select_sign.className = 'form-control p-0'
            select_sign.id = 'select_tp_lm_sign_edit_' + lm_number
            select_sign.innerHTML = '<option value="+">+</option><option value="-">-</option><option value="e">e</option>'
            td_3.appendChild(select_sign)
        }
    }
    let td_4 = document.createElement('td')
    td_4.className = 'col-1'
    tr.appendChild(td_4)
    let button_delete = document.createElement('button')
    button_delete.className = 'btn btn-outline-danger'
    button_delete.innerText = 'X'
    button_delete.setAttribute('onclick', 'this.parentNode.parentNode.remove()')
    td_4.appendChild(button_delete)
    this_button.remove()
}


// dpolc = draw_params_of_linkMap_contract
function dpolc(params, table, method, is_create=false){
    let slice_number = (is_create) ? 22 : 15
    let contract_number = table.id.slice(slice_number)
    let table_body = table.lastChild
    let is_new = (typeof params[0] === 'string' && params[0] === 'new')
    if (is_new){
        let button_id = (is_create) ? '#b_add_lm_param_create' : '#b_add_lm_param'
        $(button_id + contract_number).remove()
    }
    for (let j = 0; j < params.length; j++){
        let current_tr = document.createElement('tr')
        current_tr.className = 'row'
        table_body.appendChild(current_tr)
        let td_id = document.createElement('td')
        td_id.className = 'col-1 text-right'
        td_id.style = "word-wrap: normal"
        if (is_new){
            let input_param_id = document.createElement('input')
            input_param_id.className = 'form-control px-0'
            input_param_id.id = 'i_' + contract_number + '_param_headernew'
            if (is_create)
                input_param_id.id += '_create'
            input_param_id.type = 'number'
            td_id.appendChild(input_param_id)
            td_id.classList.add('px-0')
        }
        else
            td_id.innerText = params[j].id
        current_tr.appendChild(td_id)
        let td_val = document.createElement('td')
        td_val.className = 'col'
        current_tr.appendChild(td_val)
        let ta_val = document.createElement('textarea')
        ta_val.className = 'form-control'
        if (is_new)
            ta_val.id = 'ta_' + contract_number + '_param_codenew'
        else{
            ta_val.id = 'ta_' + contract_number + '_param' + params[j].id
            ta_val.value = params[j].value
        }
        if (is_create)
            ta_val.id += '_create'
        ta_val.style.minHeight = '1rem'
        td_val.appendChild(ta_val)
        let td_sign = document.createElement('td')
        td_sign.className = (method === 'wo') ? 'col-2' : 'col-1'
        current_tr.appendChild(td_sign)
        if (method === 'wo'){
            let input_limit = document.createElement('input')
            input_limit.className = 'form-control text-right'
            input_limit.type = 'number'
            input_limit.value = (is_new) ? 0 : params[j].limit
            input_limit.id = 'i_' + contract_number + '_limit'
            input_limit.id += (is_new) ? 'new': params[j].id
            td_sign.appendChild(input_limit)
        }
        else{
            let select_sign = document.createElement('select')
            select_sign.className = 'border border-light'
            select_sign.innerHTML = '<option>e</option><option>+</option><option>-</option>'
            select_sign.value = (is_new) ? 'e' : params[j].sign
            select_sign.id = 's_' + contract_number + '_sign'
            select_sign.id += (is_new)? 'new' : params[j].id
            if (is_create)
                select_sign.id += '_create'
            td_sign.appendChild(select_sign)
        }
        let td_del = document.createElement('td')
        td_del.className = 'col-1'
        current_tr.appendChild(td_del)
        let but_del = document.createElement('button')
        but_del.type = 'button'
        but_del.className = 'btn border-0 btn-outline-danger'
        but_del.innerText = 'X'
        but_del.setAttribute('onclick', 'this.parentNode.parentNode.remove()')
        td_del.appendChild(but_del)
    }
}


// cwo - change write off
function cwo(this_select) {
    let contract_number = this_select.id.slice(9)
    // Работаем с кодом
    let code_disabled = (this_select.value === 'n')
    $('#ta_code' + contract_number).attr('disabled', code_disabled)
    erandrat(contract_number, this_select.value)
}


// palimafos = pack link_map for save
function palimafos(is_task=false){
    let link_map = []
    $('span[id^="show_contract_id"]').each(function(){
        let i = this.id.slice(17)
        let contract_id = this.innerText
        let obj = {'class_id': parseInt(contract_id)}
        if (is_task)
            obj.loc = $('input[name="r_datatype_' + i + '"]:checked')[0].id.slice(11, 12)
        else obj.loc = 'c'
        obj['code'] = $('#ta_code' + i).val()
        obj['method'] = $('#s_method_' + i).val()
        obj['event_kind'] = []
        if (is_task)
            obj['event_kind'].push('u')
        else{
            $('input[id^="chb_event_' + i + '"]').each(function(ind) {
                if (this.checked)
                    obj['event_kind'].push(this.value)
            })
        }

        if (obj.method !== 'n'){
            // Работа с праметрами редактирования объекта
            let params = []
            let my_params = $('textarea[id^="ta_' + i+ '_param"]')
            for (let j = 0; j < my_params.length; j++){
                if (my_params[j].id.slice(-6) === 'create')
                    continue
                let param = {}
                let id = my_params[j].id.match(/ta_\d+_param(\w+)/)[1]
                if (id === '_codenew'){
                    id = 'new'
                    param['id'] = parseInt($('#i_' + i + '_param_headernew').val())
                    if (!param.id)
                        continue
                    param['value'] = my_params[j].value
                }
                else{
                    param['id'] = parseInt(id)
                    param['value'] = my_params[j].value
                }
                if (obj['method'] === 'wo')
                    param['limit'] = parseInt($('#i_' + i + '_limit' + id).val())
                else
                    param['sign'] = $('#s_' + i + '_sign' + id).val()
                params.push(param)
            }
            obj['params'] = params
            }
        if (['n', 'en'].includes(obj['method'])){
                // Работа с параметрами создания объекта
            let create_params = []
            let my_params = $('textarea[id^="ta_' + i+ '_param"]')
            for (let j = 0; j < my_params.length; j++){
                if (my_params[j].id.slice(-6) !== 'create')
                    continue
                let param = {}
                let id = my_params[j].id.match(/ta_\d+_param(\w+)_create/)[1]
                if (id === '_codenew'){
                    id = 'new'
                   param['id'] = parseInt($('#i_' + i + '_param_headernew_create').val())
                    if (!param.id)
                        continue
                    param['value'] = my_params[j].value
                }
                else{
                    param['id'] = parseInt(id)
                    param['value'] = my_params[j].value
                }
                param['sign'] = $('#s_' + i + '_sign' + id + '_create').val()
                create_params.push(param)
            }
            obj['create_params'] = create_params
        }
        link_map.push(obj)
    })

    let new_contract_id = $('#i_contract_id_new')
    if (new_contract_id.length && new_contract_id.val()){
        let new_obj = {'class_id': parseInt(new_contract_id.val())}
        if (is_task)
            new_obj.loc = $('input[name="r_datatype_new"]:checked')[0].id.slice(11, 12)
        else new_obj.loc = 'c'
        new_obj.code = $('#ta_codenew').val()
        new_obj.method = $('#s_method_new').val()
        new_obj.event_kind = []
        if (is_task)
            new_obj.event_kind.push('u')
        else{
            $('input[id^="chb_event_new"]').each(function() {
                if (this.checked)
                    new_obj['event_kind'].push(this.value)
            })
        }
        // Работаем с параметрами редактирования обекта
        if (new_obj.method !== 'n'){
            let new_params = []
            let new_param_id = $('#i_new_param_headernew')
            if (new_param_id.length && new_param_id.val()){
                let param_new = {'id': parseInt(new_param_id.val())}
                param_new.value = $('#ta_new_param_codenew').val()
                if (new_obj.method === 'wo')
                    param_new.limit = parseInt($('#i_new_limitnew').val())
                else
                    param_new.sign = $('#s_new_signnew').val()
                new_params.push(param_new)
            }
            new_obj.params = new_params
        }

        // Работаем с параметрами создания
        if (['n', 'en'].includes(new_obj.method)){
            let create_params = []
            let create_param_id = $('#i_new_param_headernew_create')
            if (create_param_id.length && create_param_id.val()){
                let param_new = {'id': parseInt(create_param_id.val())}
                param_new.value = $('#ta_new_param_codenew_create').val()
                param_new.sign = $('#s_new_signnew_create').val()
                create_params.push(param_new)
            }
            new_obj.create_params = create_params
        }
        link_map.push(new_obj)
    }
    return link_map
}


// erandrat = erease and draw table
function erandrat(contract_number, method){
    let div_edit_table = $('#div_edit_table_' + contract_number)
    div_edit_table.html('')
    if (['e', 'en', 'wo', 'pe'].includes(method)){
        let type = (method === 'wo') ? 'w' : 'e'
        dratab(div_edit_table, contract_number, type)
    }
    let div_create_table = $('#div_create_table_' + contract_number)
    div_create_table.html('')
    if (['n', 'en'].includes(method))
        dratab(div_create_table, contract_number, 'n')
}

// type = [n, e, w]
function dratab(div_table, contract_number, type){
    let input_group_params_create = document.createElement('div')
    input_group_params_create.className = 'input-group mb-1'
    div_table.append(input_group_params_create)
    let header = 'Параметры '
    header += (type === 'n') ? 'создания' : 'редактирования'
    header += ' объекта'
    let str_create = (type === 'n') ? '_create' : ''
    let is_wo = (type === 'w') ? 'wo': 'e'
    input_group_params_create.innerHTML = '<span class="input-group-text border-0 bg-transparent text-left">' +
         header + '</span><button class=" btn btn-outline-info" id="b_add_lm_param' + str_create
        + contract_number + '" ' + 'onclick="apicilm(this, \'' + is_wo + '\')">+</button>'
    let create_params_table = document.createElement('table')
    create_params_table.className = 'table table-bordered border-0'
    create_params_table.id = 'table_lm_params' + str_create + contract_number
    str_table_html = '<thead><tr class="row"><th class="col-1 text-right">ID</th>' +
        '<th class="col text-center" >Значение</th>'
    if (type === 'w')
        str_table_html += '<th class="col-2 text-center" style="white-space: nowrap;">Лимит</th>'
    else str_table_html += '<th class="col-1 text-center" style="white-space: nowrap;">Знак</th>'
    str_table_html += '<th class="col-1"></th></tr></thead><tbody></tbody>'
    create_params_table.innerHTML = str_table_html
    div_table.append(create_params_table)
}
