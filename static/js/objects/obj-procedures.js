
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