// Получить параметр из get
function get_param_from_url(param) {
    let url = window.location.href
    let re = new RegExp('(?:\\?|\\&)' + param + '=(\\d+)')
    let result = url.match(re)
    if (result)
        return result[1]
    else
        return null
    // let searchParams = new URLSearchParams(url);
    // return searchParams.get(param)
}


// Удалить параметр из get
function del_param_from_url(param, url) {
    let re = new RegExp( param + '=(\\d+)&')
    let re_end = new RegExp(param + '=(\\d+)$')
    return url.replace(re, '').replace(re_end, '')
}


function get_path_from_url() {
    let url = window.location.href
    let re = new RegExp('^.+\\/([\\w-]+).*$')
    let result = url.match(re)
    if (result)
        return result[1]
    else
        return null
}
