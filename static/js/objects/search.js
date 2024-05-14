function change_search(this_tag) {
    if (this_tag.id.slice(0, 2) === 'sf'){
        let header_id = this_tag.id.slice(2)
        let my_name = ''
        let my_val = ''
        if (header_id === 'code'){
            my_name = 'code'
            my_val = this_tag.value
            let other_filters_class = (my_val.length) ? 'tag-invis' : ''
            $('#div_other_search_filters').attr('class', other_filters_class)
            let all_filters = $('div[id^="dsf"]')
            for (let i = 0; i < all_filters.length; i++){
                if (all_filters[i].id !== 'dsfcode')
                    remove_search_filter(all_filters[i].children[0])
                else if (!my_val.length){
                    remove_search_filter(all_filters[i].children[0])
                    return false
                }
            }
        }
        else {
            if (header_id === 'dtc'){
                my_name = 'Дата и время создания'
                my_val = $('#sfsigndtc').val() + this_tag.value
            }
            else{
               my_name = JSON.parse($('#header_info' + header_id).html()).name
            let my_sign = $('#sfsign' + header_id)
            if (my_sign.length)
                my_val += my_sign.val()
            if (this_tag.nodeName.toLowerCase() === 'input' && this_tag.type === 'checkbox')
                my_val += this_tag.checked
            else my_val += this_tag.value
            }
        }
        let val = my_name + ': ' + my_val + '<span class="px-2" onclick="remove_search_filter(this)">&#10005;</span>'
        let my_data_filter = $('#dsf' + header_id)
        if (!my_data_filter.length){
            my_data_filter = document.createElement('div')
            my_data_filter.className = 'm-1 pl-1 bg-secondary text-white'
            my_data_filter.id = 'dsf' + header_id
            $('#div_search_results').append(my_data_filter)
        }
        else my_data_filter = my_data_filter[0]
        my_data_filter.innerHTML = val
    }
    else{
        let find_ids = this_tag.id.match(/ar(\d+)sf(\d+)/)
        let array_id = find_ids[1]
        let array = arrays.find((el) => el.id === parseInt(array_id))
        let header_id = find_ids[2]
        let header = array.headers.find((el) => el.id === parseInt(header_id))
        let div_array = $('#darsf' + array_id)
        if (div_array.length)
            div_array = div_array[0]
        else{
            div_array = document.createElement('div')
            div_array.className = 'm-1 pl-1 bg-secondary text-white'
            div_array.id = 'darsf' + array_id
            let array_info = JSON.parse($('#header_info' + array_id).html())
            div_array.innerText = 'Массив "' + array_info.name + '" '
            div_array.innerHTML += '<span class="px-2" onclick="remove_search_filter(this)">&#10005;</span>'
            $('#div_search_results').append(div_array)
        }
        let my_span = $('#ssf' + header_id)
        if (my_span.length)
            my_span = my_span[0]
        else{
            my_span = document.createElement('span')
            my_span.id = 'ssf' + header_id
            my_span.className = 'px-2'
            div_array.insertBefore(my_span, div_array.lastChild)
        }
        let my_sign = $('#ar' + array_id + 'sfsign' + header_id)
        my_sign = (my_sign.length) ? my_sign.val() : ''
        let my_val = (header.formula === 'bool') ? this_tag.checked : this_tag.value
        my_span.innerText = header.name + ': ' + my_sign + my_val
    }
}

function remove_search_filter(this_filter){
    if (this_filter.parentElement.id.slice(0,3) === 'dsf'){
        let my_id = this_filter.parentElement.id.slice(3)
        let link_filter = $('#sf' + my_id)[0]
        if (link_filter.tagName === 'SELECT'){
            link_filter.selectedIndex = 0
            $('#da_sf' + my_id).html('')
        }
        else if (link_filter.type === 'checkbox')
            link_filter.checked = false
        else {
         link_filter.value = ''
         if (link_filter.hasAttribute("list")){
             glas(link_filter)
             pls(link_filter)
         }
        }
        if (this_filter.parentElement.id === 'dsfcode')
            $('#div_other_search_filters').prop('class', '')
        this_filter.parentElement.remove()
    }
    else
        $('#chb_switcher' + this_filter.parentElement.id.slice(5)).click()
}

function pack_search(){
    let search_params = $('div[id^="dsf"]')
    let list_search_params = []
    for (let i = 0; i < search_params.length; i++){
        let head_id = search_params[i].id.slice(3)
        let tag_val = $('#sf' + head_id)[0]
        if (head_id === 'code'){
            list_search_params.push({'code': parseInt(tag_val.value)})
            break
        }
        else if (head_id === 'dtc')
            list_search_params.push({'dtc': $('#sf' + head_id).val(), 'sign': $('#sfsigndtc').val()})
        else{
            let header = JSON.parse($('#header_info' + head_id).html())
            let val = ''
            if (header.formula === 'float')
                val = parseFloat(tag_val.value)
            else if (['link', 'const'].includes(header.formula))
                val = parseInt(tag_val.value)
            else if (header.formula === 'bool')
                val = tag_val.checked
            else val = tag_val.value
            let param = {'header_id': header.id, 'value': val, 'type': header.formula}
            if (['float', 'date', 'datetime'].includes(header.formula))
                param['sign'] = $('#sfsign' + head_id).val()
            list_search_params.push(param)
        }
    }
    // Пройдемся по массивам
    let ar_search_params = $('div[id^="darsf"]')
    for (let i = 0; i < ar_search_params.length; i++){
        let array_id = parseInt(ar_search_params[i].id.slice(5))
        let tags = $('#darsf' + array_id).find($('span[id^="ssf"]'))
        let array = arrays.find((el) => el.id === array_id)
        let param = {'array_id': array_id, data: []}
        for (let j = 0; j < tags.length; j++){
            let header_id = parseInt(tags[j].id.slice(3))
            header = array.headers.find((el) => el.id === header_id)
            let tag_val = $('#ar' + array_id + 'sf' + header_id)[0]
            let val
            if (header.formula === 'bool')
                val = tag_val.checked
            else if (header.formula === 'float')
                val = parseFloat(tag_val.value)
            else if (['link', 'const'].includes(header.formula))
                val = parseInt(tag_val.value)
            else val = tag_val.value
            let data_param = {'header_id': header.id, 'value': val, 'type': header.formula}
            if (['float', 'date', 'datetime'].includes(header.formula))
                data_param['sign'] = $('#ar' + array_id + 'sfsign' + header_id).val()
            param.data.push(data_param)
        }
        list_search_params.push(param)
    }
    $('#i_search_filter').val(JSON.stringify(list_search_params))
}

function fill_search_filter(){
    let search_filter = JSON.parse($('#i_search_filter').val())
    if (search_filter.length){
        for (let i = 0; i < search_filter.length; i++){
            let my_tag
            if ('code' in search_filter[i]){
                my_tag = $('#sfcode')
                my_tag.val(search_filter[i].code)
                change_search(my_tag[0])
                break
            }
            else if ('dtc' in search_filter[i]){
                my_tag = $('#sfdtc')
                my_tag.val(search_filter[i].dtc)
                $('#sfsigndtc').val(search_filter[i].sign)
            }
            else if ('array_id' in search_filter[i]){
                $('#chb_switcher' + search_filter[i].array_id)[0].click()
                for (let j = 0; j < search_filter[i].data.length; j++){
                    let req = search_filter[i].data[j]
                    let tag = $('#ar' + search_filter[i].array_id + 'sf' + req.header_id)
                    if (req.type === 'bool')
                        tag.prop('checked', req.value)
                    else tag.val(req.value)
                    change_search(tag[0])
                }
            }
            else{
                my_tag = $('#sf' + search_filter[i].header_id)
                if (search_filter[i].type === 'bool')
                    my_tag.attr('checked', search_filter[i].value)
                else {
                    my_tag.val(search_filter[i].value)
                    if (['float', 'date', 'datetime'].includes(search_filter[i].type))
                        $('#sfsign' + search_filter[i].header_id).val(search_filter[i].sign)
                }
            }
            change_search(my_tag[0])
        }
    }
}

// aha = add/hide array
function aha(this_chb){
    let array_id = this_chb.id.slice(12)
    let div_array = $('#divarsf' + array_id)
    if (this_chb.checked)
        div_array.attr('class', 'ml-3 mr-1 border')
    else{
        $('[id^="ar' + array_id + 'sf"]').val('')
        $('#darsf' + array_id).remove()
        div_array.attr('class', 'tag-invis')
    }
}

// uch = uoload_const_headers
function uch(this_select, loc){
    if (this_select.children.length)
        return ''
    let header_id = this_select.id.match(/ar\d+sf(\d+)/)[1]
    $.ajax({url:'uch',
        method:'get',
        dataType:'json',
        data: {header_id: header_id, loc: loc},
        success:function(data){
            this_select.innerHTML = ''
            for (let i = 0; i < data.length; i++){
                let op = document.createElement('option')
                op.value = data[i].id
                op.innerText = data[i].name
                this_select.appendChild(op)
            }
        },
        error: function () {
            this_select.innerHTML = 'Ошибка'
        }
    })
}

// ras = recount_alias_seach
function ras(this_select) {
    let header_id = (this_select.id.slice(0, 2) === 'sf') ? this_select.id.slice(2) : this_select.id.match(/.+sf(\d+)/)[1]
    let val = this_select.value
    let path = get_path_from_url()
    let is_contract = null
    if (['manage-object', 'table-draft'].includes(path))
        is_contract = false
    else if (path === 'tree'){
        if (get_param_from_url('location') === 'c')
            is_contract = true
    }
    else is_contract = true
    let result = $('#da_sf' + header_id)
    $.ajax({url:'retreive-const',
        method:'get',
        dataType:'text',
        data: {header_id: header_id, val: val, is_contract: is_contract},
        success:function(data){
            result.html(data)
        },
        error: function () {
            result.html('error')
        }
    })

}