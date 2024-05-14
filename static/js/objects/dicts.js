// Управление объектами словарей на странице контракта / справочника

// обновить данные словаря
function update_dict(dict_id) {
    let result = {}
    result.id = dict_id
    let all_fields = $('[id*="' + dict_id + '|"]')
    all_fields.toArray().forEach((e) => {
        let int_id = e.id.match(/\|(\d+)$/)[1]
        let val
        if (e.type === 'checkbox')
            val = (e.checked)? 'True': 'False'
        else val = e.value
        result[int_id] = val
    })
    $('#dict_info' + dict_id).val(JSON.stringify(result))
}

function add_dict() {
    let div_wrapper_dicts = $('#div_wrapper_dicts')[0]
    let select = $('#new_dict')[0]
    let dict_id = select.value
    // Работаем с выпадающим списком
    for (let i = 0; i < select.children.length; i++){
        if (select.options[i].value == dict_id){
            select.remove(i)
            break
        }
    }
    let footer = $('#div_footer_dict')
    if (!select.children.length)
        footer.attr('class', 'tag-invis')
    else footer.attr('class', 'input-group mb-3')
    // Заполним словарь умолчаниями
    let header_dict = JSON.parse($('#header_dict' + dict_id).html())
    let dict = {}
    header_dict.children.forEach((e) =>{
        dict[e.id] = {'name': e.name, 'type': e.formula }
        let val
        if (e.formula === 'enum')
            val = e.default[0]
        else if (e.formula === 'link'){
            val = e.default.match(/(?:table|contract)\.\d+\.(\d*)/)[1]
        }
        else val = e.default
        dict[e.id]['value'] = val
    })
    let wrapper = document.createElement('div')
    wrapper.className = 'input-group mb-3'
    div_wrapper_dicts.appendChild(wrapper)
    let span = document.createElement('span')
    span.className = 'input-group-text'
    span.innerText = header_dict.name
    wrapper.appendChild(span)
    let div_dict = document.createElement('div')
    div_dict.className = 'form-control'
    div_dict.style = 'display: initial; width: initial; height: initial; padding: 0; border: 0'
    wrapper.appendChild(div_dict)
    fill_dict(dict, header_dict, div_dict)
    // заполним инпут
    update_dict(dict_id)
}

function fill_dict(dict, header, wrapper) {
    for (let l in dict){
        if (parseInt(l)){
            let div = document.createElement('div')
            div.className = 'input-group'
            let key = document.createElement('span')
            key.className = 'input-group-text'
            key.style = 'background-color: white; border: 0'
            key.innerText = dict[l]['name']
            div.appendChild(key)
            let val
            // Для перечислений
            if(dict[l]['type'] === 'enum'){
                val = document.createElement('select')
                val.className = 'form-control'
                for (let i = 0; i < header['children'].length; i++){
                    if (header['children'][i].id == parseInt(l)){
                        let array_enum = header['children'][i].default
                        array_enum.forEach((e, j) =>{
                            let opt = document.createElement('option')
                            opt.id = e
                            opt.innerText = e
                            val.appendChild(opt)
                            if (e == dict[l]['value'])
                                val.selectedIndex = j
                        })
                        break
                    }
                }
            }
            // для булевых данных
            else if (dict[l]['type'] === 'bool'){
                val = document.createElement('input')
                val.type = 'checkbox'
                val.className = 'form-control'
                val.style = 'height: calc(1rem + 2px); margin: auto'
                let is_checked = (dict[l]['value'] === 'True')
                val.checked = is_checked
            }
            // Дата или дата-время
            else if (['date', 'datetime'].includes(dict[l]['type'])){
                val = document.createElement('input')
                val.type = (dict[l]['type'] == 'date') ? 'date': 'datetime-local'
                val.className = 'form-control'
                val.value = dict[l]['value']
            }
            // Для остальных типов данных
            else{
                val = document.createElement('input')
                val.className = 'form-control'
                if (['float', 'link'].includes(dict[l]['type']))
                    val.type = 'number'
                val.value = dict[l]['value']
            }
            val.id = header.id + '|' + l
            val.setAttribute('oninput', 'update_dict(' + header.id + ')')
            div.appendChild(val)
            wrapper.appendChild(div)
            // для ссылок добавим подсказку и список
            if (dict[l].type === 'link'){
                let dl = document.createElement('datalist')
                dl.id = 'dl_dict_link_' + l
                div.appendChild(dl)
                let s = document.createElement('span')
                s.className = 'input-group-text'
                s.id = 's_dict_link_' + l
                div.appendChild(s)
                val.setAttribute('list', dl.id)
                val.setAttribute('oninput', 'dict_link_promp(this), update_dict(' + header.id + ')')
                dict_link_promp(val, false)
            }
        }
    }
    // Кнопка удалить словарь
    let del_but = document.createElement('input')
    del_but.type = 'button'
    del_but.className = 'btn btn-outline-danger'
    del_but.value = 'Удалить'
    del_but.id = 'del_but' + header.id
    del_but.setAttribute('onclick', 'del_dict(this)')
    wrapper.appendChild(del_but)
}

function del_dict(delete_button){
    let dict_id = delete_button.id.slice(7)
    $('#delete_dict').val(dict_id)
    $('#delete_dict_modal').modal('show');
}

function dict_link_promp(this_input, delay_promp=true){
    function do_this(){
        let match = this_input.id.match(/(\d+)\|(\d+)/)
        let dict_id = match[1]
        let header_id = match[2]
        let header_info = JSON.parse($('#header_dict' + dict_id).text())
        let code = this_input.value
        let str_default = ''
        for (let i = 0; i < header_info.children.length; i++){
            if (header_info.children[i].id === parseInt(header_id)){
                str_default = header_info.children[i].default
                break
            }
        }
        let match_link = str_default.match(/^(table|contract)\.(\d+)\./)
        let datalist = $('#dl_dict_link_' + header_id)
        datalist.html('')
        $.ajax({url:'gon4d',
            method:'get',
            dataType:'json',
            data: {link_type: match_link[1], link_id: match_link[2], code: code},
            success:function(data){
                if (!(typeof data === 'object' && 'error' in data)){
                    for (let i = 0; i < data.length; i++){
                        let op = document.createElement('option')
                        op.value = data[i].code
                        op.innerText = (match_link[1] === 'contract') ? data[i].value.datetime_create : data[i].value
                        datalist.append(op)
                    }
                }
                // Заполним подсказку
                let s_def = $('#' + 's_dict_link_' + header_id)
                s_def.text('')
                let arr_dl = datalist.children().toArray()
                let obj_is_correct = false
                for (let i = 0; i < arr_dl.length; i++){
                    if (code === arr_dl[i].value){
                        let url = (match_link[1] === 'table') ? 'manage-object' : 'contract'
                        let link_text = '<a target="_blank" href="/' + url + '?class_id=' + match_link[2] +
                            '&object_code=' + code + '">' + arr_dl[i].innerText + '</a>'
                        s_def.html(link_text)
                        obj_is_correct = true
                        break
                    }
                }
                if (!code)
                    obj_is_correct = true
                $('#b_save').attr('disabled', !obj_is_correct)
            },
            error: () => {$('#i_link_def').val('Ошибка')}
        })
    }
    if (delay_promp){
        clearTimeout(typingTimer)
        typingTimer = setTimeout(do_this, 1500)
    }
    else do_this()

}