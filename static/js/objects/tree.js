var array_timeline = {}

function new_branch() {
    $('#i_code').val('')
    $('#i_name').val('')
    $('#i_parent').val('')
    $('.table-active').removeClass('table-active')
    // динамическая часть
    let headers = $('[id^="header_info"]')
    for (let i = 0; i < headers.length; i++){
        let header = JSON.parse(headers[i].innerHTML)
        if (header.formula === 'bool'){
            if (header.default === 'True')
                $('#chb_bool_' + header.id).prop('checked', true)
            else
                $('#chb_bool_' + header.id).prop('checked', false)
        }
        else if (header.formula === 'float')
            $('#i_float_' + header.id).val(header.default)
        else if (header.formula === 'string')
            $('#ta_' + header.id).val(header.default)
        else if (header.formula === 'link'){
            $('#i_link_' + header.id).val(header.default)
            if (header.default)
                fast_get_link($('#i_link_' + header.id)[0],  header.value[0])
            else
                $('#s_link_' + header.id).html('')
        }
        else if (header.formula === 'datetime')
            $('#i_datetime_' + header.id).val(header.default)
        else if (header.formula === 'date')
            $('#i_date_' + header.id).val(header.default)
        else if (header.formula === 'enum')
            $('#s_enum_' + header.id).prop('selectedIndex', 0)
        else if (header.formula === 'eval')
            $('#div_eval_' + header.id).html('')
        else if (header.formula === 'const'){
            $('#div_alias_' + header.id).html('')
            let alias = $('#s_alias_' + header.id)
            let array = alias.children().toArray()
            for (let j = 0; j < array.length; j++){
                if (array[j].value === header.default){
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


window.onload = function () {
    array_timeline = JSON.parse($('#div_array_timeline').html())
}