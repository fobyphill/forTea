
// cfiff = create_file_input_for_fact
function cfiff(header_id) {
    let my_folder = $('#i_filename_' + header_id).parent()
    let my_file = document.createElement('input')
    my_file.id = 'i_file_' + header_id
    my_file.name = 'i_file_' + header_id
    my_file.type = 'file'
    my_file.className = 'custom-file-input'
    my_file.setAttribute('oninput', 'change_file_label(this)')
    my_folder.append(my_file)
}

let dict_type_prefix = {'float': '#i_float_', 'string': '#ta_', 'link': '#i_link_', 'bool': '#chb_',
        'date': '#i_date_', 'datetime': '#i_datetime_', 'enum': '#s_enum_', 'const': '#s_alias_', 'file': '#i_file_'}


// oorbh = on_off_req_by_handler
function oorbh(header, off, is_contract) {
    let my_style
    if (header.formula === 'bool') {
        let my_tag = $(dict_type_prefix[header.formula] + header.id)
        if (off)
            my_tag.attr('onclick', 'return false')
        else my_tag.attr('onclick', '')
    }
    else if (header.formula === 'datetime'){
        let rodt = (header.name === 'system_data' && is_contract) ? true : off
        $(dict_type_prefix[header.formula] + header.id).attr('readonly', rodt)
        }
    else if (['enum', 'const'].includes(header.formula)){
        my_style = (off) ? 'pointer-events: none; background-color: #e9ecef' : ''
        $(dict_type_prefix[header.formula] + header.id).attr('style', my_style)
        }
    else if (header.formula === 'file'){
        let my_file = $(dict_type_prefix[header.formula] + header.id)
        if (off && Boolean(my_file.length))
            my_file.remove()
        else if (!my_file.length)
            cfiff(header.id)
        }
    else
        $(dict_type_prefix[header.formula] + header.id).attr('readonly', off)
}