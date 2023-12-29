function new_branch() {
    $('#i_code').val('')
    $('#i_name').val('')
    $('#i_parent').val('')
    $('.table-active').removeClass('table-active')
    // динамическая часть
    let headers = JSON.parse($('#div_headers').html())
    for (let i = 0; i < headers.length; i++){
        if (headers[i].formula === 'bool'){
            if (headers[i].default === 'True')
                $('#chb_bool_' + headers[i].id).prop('checked', true)
            else
                $('#chb_bool_' + headers[i].id).prop('checked', false)
        }
        else if (headers[i].formula === 'float')
            $('#i_float_' + headers[i].id).val(headers[i].default)
        else if (headers[i].formula === 'string')
            $('#ta_string_' + headers[i].id).val(headers[i].default)
        else if (headers[i].formula === 'link'){
            $('#i_link_' + headers[i].id).val(headers[i].default)
            if (headers[i].default){
                let is_contract = (headers[i].value[0] === 'c')
                get_link_ajax($('#i_link_' + headers[i].id)[0], is_contract)
            }
            else
                $('#s_link_' + headers[i].id).html('')
        }
        else if (headers[i].formula === 'datetime')
            $('#i_datetime_' + headers[i].id).val(headers[i].default)
        else if (headers[i].formula === 'date')
            $('#i_date_' + headers[i].id).val(headers[i].default)
        else if (headers[i].formula === 'enum')
            $('#s_enum_' + headers[i].id).prop('selectedIndex', 0)
        else if (headers[i].formula === 'eval')
            $('#div_eval_' + headers[i].id).html('')
        else if (headers[i].formula === 'const'){
            $('#div_alias_' + headers[i].id).html('')
            let alias = $('#s_alias_' + headers[i].id)
            let array = alias.children().toArray()
            for (let j = 0; j < array.length; j++){
                if (array[j].value === headers[i].default){
                    alias.prop('selectedIndex', j)
                    recount_alias(alias[0])
                    break
                }
            }
        }
    }
}

function select_table_branch(this_li) {
    $('.table-active').removeClass('table-active')
    this_li.className = 'row table-active'
    let code = this_li.id.slice(4)
    send_form_with_param('branch_code', code)
}