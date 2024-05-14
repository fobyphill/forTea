// acilm = add contract in linkMap
function acilm(link_map=null){
    let b_add_class = $('#b_acilm')[0]
    if (typeof link_map === 'string' && link_map === 'new')
        link_map = [{'contract': 'new', 'code': '', 'new_code': false, 'writeoff': false, 'params': []}]
    if (!link_map)
        return false
    for (let i = link_map.length - 1; i >= 0; i--){
        let div_contract = document.createElement('div')
        div_contract.id = 'div_lm_contract_' + link_map[i].contract
        b_add_class.after(div_contract)
        if (link_map[i].contract === 'new')
            b_add_class.remove()
        let hr = document.createElement('hr')
        hr.className = 'border border-secondary'
        div_contract.appendChild(hr)
        let input_group_id = document.createElement('div')
        input_group_id.className = 'input-group mb-1'
        div_contract.appendChild(input_group_id)
        let span_contract_id = document.createElement('span')
        span_contract_id.className = 'input-group-text border-0 bg-transparent text-left'
        span_contract_id.innerText = 'ID контракта'
        input_group_id.appendChild(span_contract_id)
    if (link_map[i].contract === 'new'){
        let input_contract_id = document.createElement('input')
        input_contract_id.className = 'form-control'
        input_contract_id.id = 'i_contract_id_new'
        input_contract_id.type = 'number'
        input_group_id.appendChild(input_contract_id)
    }
    else{
        let show_contract_id = document.createElement('span')
        show_contract_id.className = 'form-control'
        show_contract_id.id = 'show_contract_id'
        show_contract_id.innerText = link_map[i].contract
        input_group_id.appendChild(show_contract_id)
    }
    let but_del = document.createElement('button')
    but_del.type = 'button'
    but_del.className = 'btn border-0 btn-outline-danger'
    but_del.innerText = 'X'
    but_del.setAttribute('onclick', 'this.parentNode.parentNode.remove()')
    input_group_id.appendChild(but_del)
    // Код
    let input_group_code = document.createElement('div')
    input_group_code.className = 'input-group mb-1'
    div_contract.appendChild(input_group_code)
    let span_code = document.createElement('span')
    span_code.className = 'input-group-text border-0 bg-transparent text-left'
    span_code.innerText = 'Код'
    input_group_code.appendChild(span_code)
    let input_code = document.createElement('input')
    input_code.className = 'form-control'
    input_code.id = 'i_code' + link_map[i].contract
    input_code.value = link_map[i].code
    input_group_code.appendChild(input_code)
    let span_or_new = document.createElement('span')
    span_or_new.className = 'input-group-text border-0 bg-transparent text-left'
    span_or_new.innerText = 'или новый'
    input_group_code.appendChild(span_or_new)
    let chb_or_new = document.createElement('input')
    chb_or_new.type = 'checkbox'
    chb_or_new.checked = link_map[i].new_code
    chb_or_new.id = 'chb_or_new' + link_map[i].contract
    input_group_code.appendChild(chb_or_new)
    // списание
    let input_group_writeoff = document.createElement('div')
    input_group_writeoff.className = 'input-group mb-1'
    div_contract.appendChild(input_group_writeoff)
    input_group_writeoff.innerHTML = '<span class="input-group-text border-0 bg-transparent text-left">Списание</span>'
    let chb_wo = document.createElement('input')
    chb_wo.type = 'checkbox'
    chb_wo.checked = link_map[i].writeoff
    chb_wo.id = 'chb_wo' + link_map[i].contract
    chb_wo.setAttribute('onclick', 'cwo(this)')
    input_group_writeoff.appendChild(chb_wo)
    if (chb_wo.checked)
        chb_or_new.disabled = true

    // параметры
    let input_group_params = document.createElement('div')
    input_group_params.className = 'input-group mb-1'
    div_contract.appendChild(input_group_params)
    input_group_params.innerHTML = '<span class="input-group-text border-0 bg-transparent text-left">Параметры' +
        '</span><button class=" btn btn-outline-info" id="b_add_lm_param' + link_map[i].contract + '" ' +
        'onclick="apicilm(this)">+</button>'
    let params = link_map[i].params
    let params_table = document.createElement('table')
    params_table.className = 'table table-bordered'
    params_table.style['border'] = 'None'
    params_table.id = 'table_lm_params' + link_map[i].contract
    div_contract.appendChild(params_table)
    let sign_or_limit = (link_map[i].writeoff) ? 'Лимит' : 'Знак'
    let style_sign = (link_map[i].writeoff) ? 'col-2 text-center' : 'col-1 text-center'
    let into_table = '<thead><tr class="row"><th class="col-1 text-right">ID</th>' +
        '<th class="col text-center" >Значение</th>' +
        '<th class="' + style_sign + '" style="white-space: nowrap;">' + sign_or_limit
        + '</th><th class="col-1"></th></tr></thead><tbody></tbody>'
    params_table.innerHTML = into_table
    dpolc(params, params_table)
    }
}

// apicilm = add param in contract in linkMap
function apicilm(this_button){
    let contract_id = this_button.id.slice(14)
    let params = ['new']
    let table = $('#table_lm_params' + contract_id)[0]
    dpolc(params, table)
}

// dpolc = draw_params_of_linkMap_contract
function dpolc(params, table){
    let contract_id = table.id.slice(15)
    let table_body = table.lastChild
    let is_new = (typeof params[0] === 'string' && params[0] === 'new')
    if (is_new)
        $('#b_add_lm_param' + contract_id).remove()
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
            input_param_id.id = 'i_' + contract_id + '_param_headernew'
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
        let input_val = document.createElement('input')
        input_val.className = 'form-control'
        if (is_new)
            input_val.id = 'i_' + contract_id + '_param_codenew'
        else{
            input_val.id = 'i_' + contract_id + '_param' + params[j].id
            input_val.value = params[j].value
        }
        td_val.appendChild(input_val)
        let td_sign = document.createElement('td')
        let is_wo = ($('#chb_wo' + contract_id)[0].checked)
        td_sign.className = (is_wo) ? 'col-2' : 'col-1'
        current_tr.appendChild(td_sign)
        if (is_wo){
            let input_limit = document.createElement('input')
            input_limit.className = 'form-control text-right'
            input_limit.type = 'number'
            input_limit.value = (is_new) ? 0 : params[j].limit
            input_limit.id = 'i_' + contract_id + '_limit'
            input_limit.id += (is_new) ? 'new': params[j].id
            td_sign.appendChild(input_limit)
        }
        else{
            let select_sign = document.createElement('select')
            select_sign.className = 'border border-light'
            select_sign.innerHTML = '<option>e</option><option>+</option><option>-</option>'
            select_sign.value = (is_new) ? 'e' : params[j].sign
            select_sign.id = 's_' + contract_id + '_sign'
            select_sign.id += (is_new)? 'new' : params[j].id
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
function cwo(this_chb) {
    let contract_id = this_chb.id.slice(6)
    let is_wo = this_chb.checked
    $('#chb_or_new' + contract_id)[0].disabled = is_wo
    let my_table = $('#table_lm_params' + contract_id)[0]
    // Правим заголовок
    let var_td = my_table.children[0].children[0].children[2]
    var_td.className = (is_wo) ? 'col-2' : 'col-1'
    var_td.className += ' text-center'
    var_td.innerText = (is_wo) ? "Лимит" : "Знак"
    // Правим столбцы
    let table_body = my_table.lastChild.children
    for (let i = 0; i < table_body.length; i++){
        let my_td = table_body[i].children[2]
        let re = new RegExp('[is]_' + contract_id + '_(?:limit|sign)(\\w+)')
        let header_id = my_td.children[0].id.match(re)[1]
        my_td.innerHTML = ''
        let input_code = table_body[i].children[1].children[0]

        if (is_wo){
            my_td.className = 'col-2 text-center'
            let my_input = document.createElement('input')
            my_input.className = 'form-control'
            my_input.value = 0
            my_input.type = 'number'
            my_input.id = 'i_' + contract_id + '_limit' + header_id
            my_td.appendChild(my_input)
        }
        else{
            my_td.className = 'col-1 text-center'
            let my_select = document.createElement('select')
            my_select.className = 'border border-light'
            my_select.innerHTML = '<option>e</option><option>+</option><option>-</option>'
            my_select.id = 's_' + contract_id + '_sign' + header_id
            my_td.appendChild(my_select)
        }
    }
}

// palimafos = pack link_map for save
function palimafos() {
    let link_map = []
    let exist_contracts = $('span[id="show_contract_id"]')
    for (let i = 0; i < exist_contracts.length; i++){
        let contract_id = exist_contracts[i].innerText
        let obj = {'contract': parseInt(contract_id)}
        obj['code'] = $('#i_code' + contract_id).val()
        obj['writeoff'] = $('#chb_wo' + contract_id)[0].checked
        obj['new_code'] = (obj['writeoff']) ? false : $('#chb_or_new' + contract_id)[0].checked
        let params = []
        let my_params = $('input[id^="i_' + contract_id + '_param"]')
        for (let j = 0; j < my_params.length; j++){
            let param = {}
            let id = my_params[j].id.match(/i_\d+_param(\w+)/)[1]
            if (id === '_headernew'){
                id = 'new'
               param['id'] = parseInt(my_params[j].value)
                if (!param.id)
                    continue
                param['value'] = $('#i_' + contract_id + '_param_codenew').val()
            }
            else if (id === '_codenew')
                continue
            else{
                param['id'] = parseInt(id)
                param['value'] = my_params[j].value
            }
            if (obj['writeoff'])
                param['limit'] = parseInt($('#i_' + contract_id + '_limit' + id).val())
            else
                param['sign'] = $('#s_' + contract_id + '_sign' + id).val()
            params.push(param)
        }
        obj['params'] = params
        link_map.push(obj)
    }
    let new_contract_id = $('#i_contract_id_new')
    if (new_contract_id.length && new_contract_id.val()){
        let new_obj = {'contract': parseInt(new_contract_id.val())}
        new_obj.code = $('#i_codenew').val()
        new_obj.writeoff = $('#chb_wonew')[0].checked
        new_obj.new_code = (new_obj.writeoff) ? false : $('#chb_or_newnew')[0].checked
        let new_params = []
        let new_param_id = $('#i_new_param_headernew')
        if (new_param_id.length && new_param_id.val()){
            let param_new = {'id': parseInt(new_param_id.val())}
            param_new.value = $('#i_new_param_codenew').val()
            if (new_obj.writeoff)
                param_new.limit = parseInt($('#i_new_limitnew').val())
            else
                param_new.sign = $('#s_new_signnew').val()
            new_params.push(param_new)
        }
        new_obj.params = new_params
        link_map.push(new_obj)
    }
    return link_map
}